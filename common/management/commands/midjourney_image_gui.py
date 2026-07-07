import subprocess
import threading
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from PIL import Image, ImageOps, ImageTk

from common.management.commands.manage_midjourney_catalog_images import (
    attach_image_path_to_item,
    build_midjourney_prompt,
    build_openai_prompt,
    DEFAULT_OPENAI_IMAGE_MODEL,
    DEFAULT_OPENAI_IMAGE_QUALITY,
    OPENAI_IMAGE_MODELS,
    OPENAI_IMAGE_QUALITIES,
    get_openai_image_model,
    ensure_state,
    generate_openai_images,
    item_existing_image_path,
    item_label,
    print_item,
    refresh_state_prompts,
    refresh_state_items,
    save_state,
    update_item,
)


try:
    import tkinter as tk
    from tkinter import filedialog, messagebox
except Exception as exc:  # pragma: no cover - GUI availability depends on host
    raise CommandError(f'Tkinter is required for the GUI: {exc}')


THUMB_SIZE = (420, 420)
SAVED_SIZE = (512, 512)
REVIEW_SIZE = (512, 512)


class LargeImageViewer:
    def __init__(self, parent, path):
        self.parent = parent
        self.path = Path(path)
        self.base_image = Image.open(self.path)
        self.photo_ref = None

        self.window = tk.Toplevel(parent)
        self.window.title(f'View image - {self.path.name}')
        self.window.geometry('1200x1000')
        self.window.transient(parent)

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)

        header = tk.Frame(self.window, padx=10, pady=8)
        header.grid(row=0, column=0, sticky='ew')
        header.columnconfigure(0, weight=1)

        tk.Label(header, text=self.path.name, font=('TkDefaultFont', 14, 'bold')).grid(row=0, column=0, sticky='w')
        tk.Label(header, text=str(self.path), foreground='#666').grid(row=1, column=0, sticky='w')

        controls = tk.Frame(header)
        controls.grid(row=0, column=1, rowspan=2, sticky='e')
        self.zoom_var = tk.IntVar(value=140)
        tk.Label(controls, text='Zoom').grid(row=0, column=0, sticky='e')
        tk.Scale(
            controls,
            from_=25,
            to=300,
            orient='horizontal',
            variable=self.zoom_var,
            command=lambda _value: self.render(),
            length=220,
        ).grid(row=0, column=1, sticky='e', padx=(8, 0))
        tk.Button(controls, text='Open externally', command=self.open_external).grid(row=0, column=2, sticky='e', padx=(8, 0))

        canvas_frame = tk.Frame(self.window)
        canvas_frame.grid(row=1, column=0, sticky='nsew')
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(canvas_frame, bg='#222', highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky='nsew')
        x_scroll = tk.Scrollbar(canvas_frame, orient='horizontal', command=self.canvas.xview)
        y_scroll = tk.Scrollbar(canvas_frame, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=x_scroll.set, yscrollcommand=y_scroll.set)
        x_scroll.grid(row=1, column=0, sticky='ew')
        y_scroll.grid(row=0, column=1, sticky='ns')

        self.image_id = self.canvas.create_image(0, 0, anchor='nw')
        self.render()

    def render(self):
        zoom = max(25, int(self.zoom_var.get()))
        width = max(1, self.base_image.width * zoom // 100)
        height = max(1, self.base_image.height * zoom // 100)
        image = self.base_image.resize((width, height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        self.photo_ref = photo
        self.canvas.itemconfigure(self.image_id, image=photo)
        self.canvas.config(scrollregion=(0, 0, width, height))
        self.canvas.delete('caption')
        self.canvas.create_text(
            12,
            12,
            anchor='nw',
            fill='white',
            tags='caption',
            text=f'{width} x {height}',
        )

    def open_external(self):
        subprocess.Popen(['xdg-open', str(self.path)])


class BatchReviewer:
    def __init__(self, parent, paths, on_use):
        self.parent = parent
        self.paths = [Path(path) for path in paths]
        self.on_use = on_use
        self.index = 0
        self.photo_ref = None

        self.window = tk.Toplevel(parent)
        self.window.title('Review OpenAI batch')
        self.window.geometry('980x1080')
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.transient(parent)

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(1, weight=1)

        self.title_var = tk.StringVar(value='')
        self.path_var = tk.StringVar(value='')

        header = tk.Frame(self.window, padx=12, pady=10)
        header.grid(row=0, column=0, sticky='ew')
        header.columnconfigure(0, weight=1)
        tk.Label(header, textvariable=self.title_var, font=('TkDefaultFont', 15, 'bold')).grid(row=0, column=0, sticky='w')
        tk.Label(header, textvariable=self.path_var, foreground='#888').grid(row=1, column=0, sticky='w', pady=(3, 0))

        self.image_label = tk.Label(self.window, text='No image', padx=12, pady=12)
        self.image_label.grid(row=1, column=0, sticky='nsew')

        controls = tk.Frame(self.window, padx=12, pady=10)
        controls.grid(row=2, column=0, sticky='ew')
        for col in range(4):
            controls.columnconfigure(col, weight=1)

        tk.Button(controls, text='Previous', command=self.previous).grid(row=0, column=0, sticky='ew', padx=4)
        tk.Button(controls, text='Next', command=self.next).grid(row=0, column=1, sticky='ew', padx=4)
        tk.Button(controls, text='Open file', command=self.open_file).grid(row=0, column=2, sticky='ew', padx=4)
        tk.Button(controls, text='Use this image', command=self.use_current).grid(row=0, column=3, sticky='ew', padx=4)

        self._render()

    def _render(self):
        if not self.paths:
            self.title_var.set('No generated images')
            self.path_var.set('')
            self.image_label.configure(image='', text='No image')
            return

        path = self.paths[self.index]
        image = Image.open(path)
        image.thumbnail(REVIEW_SIZE)
        photo = ImageTk.PhotoImage(image)
        self.photo_ref = photo
        self.image_label.configure(image=photo, text='')
        self.image_label.image = photo
        self.title_var.set(f'Image {self.index + 1} of {len(self.paths)}')
        self.path_var.set(str(path))

    def previous(self):
        if not self.paths:
            return
        self.index = (self.index - 1) % len(self.paths)
        self._render()

    def next(self):
        if not self.paths:
            return
        self.index = (self.index + 1) % len(self.paths)
        self._render()

    def open_file(self):
        if not self.paths:
            return
        subprocess.Popen(['xdg-open', str(self.paths[self.index])])

    def use_current(self):
        if not self.paths:
            return
        self.on_use(self.paths[self.index])
        self.close()

    def close(self):
        if self.window.winfo_exists():
            self.window.destroy()


class UnsavedItemBatchRunner:
    def __init__(self, gui, items):
        self.gui = gui
        self.items = list(items)
        self.index = 0
        self.in_flight = 0
        self.max_parallel = max(1, min(10, gui.get_batch_parallelism()))
        self.stopped = False
        self.photo_ref = None

        self.window = tk.Toplevel(gui.root)
        self.window.title('Auto batch: next unsaved items')
        self.window.geometry('1200x900')
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.transient(gui.root)

        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(2, weight=1)

        self.position_var = tk.StringVar(value='')
        self.label_var = tk.StringVar(value='')
        self.status_var = tk.StringVar(value='Starting...')
        self.file_var = tk.StringVar(value='')
        self.prompt_var = tk.StringVar(value='')

        header = tk.Frame(self.window, padx=12, pady=10)
        header.grid(row=0, column=0, sticky='ew')
        header.columnconfigure(0, weight=1)
        tk.Label(header, textvariable=self.position_var, font=('TkDefaultFont', 14, 'bold')).grid(row=0, column=0, sticky='w')
        tk.Label(header, textvariable=self.label_var).grid(row=1, column=0, sticky='w')
        tk.Label(header, textvariable=self.status_var, foreground='#666').grid(row=2, column=0, sticky='w')
        tk.Label(header, textvariable=self.file_var, foreground='#888').grid(row=3, column=0, sticky='w')

        prompt_frame = tk.LabelFrame(self.window, text='Current prompt')
        prompt_frame.grid(row=1, column=0, sticky='ew', padx=12, pady=(0, 10))
        prompt_frame.columnconfigure(0, weight=1)
        tk.Label(prompt_frame, textvariable=self.prompt_var, justify='left', wraplength=1120).grid(row=0, column=0, sticky='w', padx=8, pady=8)

        self.image_label = tk.Label(self.window, text='Auto batch running...', padx=12, pady=12)
        self.image_label.grid(row=2, column=0, sticky='nsew')

        controls = tk.Frame(self.window, padx=12, pady=10)
        controls.grid(row=3, column=0, sticky='ew')
        for col in range(4):
            controls.columnconfigure(col, weight=1)

        tk.Button(controls, text='Mark reviewed', command=self.mark_reviewed).grid(row=0, column=0, sticky='ew', padx=4)
        tk.Button(controls, text='Regenerate current', command=self.regenerate_current).grid(row=0, column=1, sticky='ew', padx=4)
        tk.Button(controls, text='Open image', command=self.open_file).grid(row=0, column=2, sticky='ew', padx=4)
        tk.Button(controls, text='Stop', command=self.close).grid(row=0, column=3, sticky='ew', padx=4)

        self.window.after(100, self.process_next)

    def current_item(self):
        if not self.items or self.index >= len(self.items):
            return None
        return self.items[self.index]

    def render_item(self):
        item = self.current_item()
        if not item:
            self.position_var.set('Done')
            self.label_var.set('Batch complete')
            self.status_var.set('All requested items have been processed.')
            self.file_var.set('')
            self.prompt_var.set('')
            self.image_label.configure(image='', text='Batch complete')
            return
        self.position_var.set(f'Item {self.index + 1} of {len(self.items)}')
        self.label_var.set(item_label(item))
        self.status_var.set(f"Status: {item.get('status')} | Route: {item.get('route')}")
        existing = item_existing_image_path(item)
        self.file_var.set(f"Existing image: {existing.name if existing else 'none'}")
        self.prompt_var.set(build_openai_prompt(item))

    def process_next(self):
        if self.stopped or not self.window.winfo_exists():
            return
        while not self.stopped and self.in_flight < self.max_parallel:
            item = self.current_item()
            if not item:
                if self.in_flight == 0:
                    self.render_item()
                    save_state(self.gui.state)
                    self.gui._populate_list()
                return
            if item_existing_image_path(item):
                update_item(item, status='awaiting_review', notes='Already had image; marked for review')
                save_state(self.gui.state)
                self.gui._populate_list()
                self.index += 1
                continue

            self.index += 1
            self.in_flight += 1
            self._launch_generation(item)

    def _launch_generation(self, item):
        prompt = build_openai_prompt(item)
        item['prompt'] = prompt
        save_state(self.gui.state)
        self.render_item()

        def do_generate():
            def log_message(message):
                print(message)
                if self.window.winfo_exists():
                    self.window.after(0, lambda: self.status_var.set(message[:180]))

            return prompt, self.gui._generate_openai_with_retries(
                item,
                prompt,
                count=1,
                model=self.gui.openai_image_model,
                quality=self.gui.openai_image_quality,
                debug=self.gui.debug_openai,
                debug_log=log_message,
            )

        def done(result, error):
            self.in_flight = max(0, self.in_flight - 1)
            if error:
                self.status_var.set(f'bad response x5, skipping: {error}')
                self.window.after(25, self.process_next)
                return
            _prompt_value, paths = result
            if not paths:
                self.status_var.set('bad response x5, skipping')
                self.window.after(25, self.process_next)
                return
            archived = self.gui.apply_image_to_item(item, paths[0], note_prefix='Auto batch')
            update_item(item, status='awaiting_review', notes=f'Auto batch from {archived.name}')
            save_state(self.gui.state)
            self.file_var.set(str(archived))
            self.status_var.set('Saved and queued for review')
            self._set_image(archived)
            self.gui._populate_list()
            self.window.after(25, self.process_next)

        self.gui._run_background(do_generate, done)

    def _set_image(self, path):
        image = Image.open(path)
        image.thumbnail((1000, 650))
        photo = ImageTk.PhotoImage(image)
        self.photo_ref = photo
        self.image_label.configure(image=photo, text='')
        self.image_label.image = photo

    def mark_reviewed(self):
        item = self.current_item()
        if not item:
            return
        update_item(item, status='reviewed', notes='Reviewed in GUI')
        save_state(self.gui.state)
        self.gui._populate_list()
        self.status_var.set('Marked reviewed')

    def regenerate_current(self):
        item = self.current_item()
        if not item:
            return
        item['prompt'] = build_openai_prompt(item)
        save_state(self.gui.state)
        self.status_var.set('Use Generate 1 for a manual retry on this item')

    def open_file(self):
        item = self.current_item()
        if not item:
            return
        path = item_existing_image_path(item)
        if not path:
            messagebox.showinfo('Rentalution', 'No saved image for this item.')
            return
        subprocess.Popen(['xdg-open', str(path)])

    def close(self):
        self.stopped = True
        if self.window.winfo_exists():
            self.window.destroy()


class MidjourneyImageGUI:
    def __init__(self, root, state):
        self.root = root
        self.state = state
        self.items = state['items']
        self.filtered_items = list(self.items)
        self.current_item = None
        self.generated_paths = []
        self.preview_refs = {}
        self.batch_reviewer = None
        self.unsaved_batch_runner = None
        self.saved_viewer = None
        self.prompt_mode = 'openai'
        self.openai_image_model = state.get('openai_image_model', DEFAULT_OPENAI_IMAGE_MODEL)
        if self.openai_image_model not in OPENAI_IMAGE_MODELS:
            self.openai_image_model = DEFAULT_OPENAI_IMAGE_MODEL
        self.openai_image_quality = state.get('openai_image_quality', DEFAULT_OPENAI_IMAGE_QUALITY)
        self.debug_openai = bool(state.get('debug_openai', False))
        self.batch_parallelism = int(state.get('batch_parallelism', 3) or 3)
        self.batch_parallelism = max(1, min(10, self.batch_parallelism))
        self.state['openai_image_model'] = self.openai_image_model
        self.state['openai_image_quality'] = self.openai_image_quality
        self.state['debug_openai'] = self.debug_openai
        self.state['batch_parallelism'] = self.batch_parallelism
        self.saved_image_path = None
        self.saved_image_photo = None
        self.search_var = tk.StringVar(value='')

        self.root.title('Rentalution image queue')
        self.root.geometry('1500x950')

        self._build_ui()
        self._populate_list()
        self.select_first_pending()

    def _build_ui(self):
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        left = tk.Frame(self.root, padx=8, pady=8)
        left.grid(row=0, column=0, sticky='nsw')
        left.rowconfigure(2, weight=1)

        tk.Label(left, text='Queue').grid(row=0, column=0, sticky='w')
        search_entry = tk.Entry(left, textvariable=self.search_var, width=44)
        search_entry.grid(row=1, column=0, sticky='ew', pady=(6, 6))
        search_entry.insert(0, '')
        self.search_var.trace_add('write', lambda *_args: self._apply_queue_search())
        self.listbox = tk.Listbox(left, width=44, height=40)
        self.listbox.grid(row=2, column=0, sticky='ns')
        self.listbox.bind('<<ListboxSelect>>', self._on_select)

        right = tk.Frame(self.root, padx=12, pady=8)
        right.grid(row=0, column=1, sticky='nsew')
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=0)
        right.rowconfigure(4, weight=12)
        right.rowconfigure(5, weight=0)
        right.rowconfigure(6, weight=0)
        right.rowconfigure(7, weight=0)

        self.title_var = tk.StringVar(value='No item selected')
        self.status_var = tk.StringVar(value='')
        self.image_note_var = tk.StringVar(value='')

        tk.Label(right, textvariable=self.title_var, font=('TkDefaultFont', 16, 'bold')).grid(row=0, column=0, sticky='w')
        tk.Label(right, textvariable=self.status_var).grid(row=1, column=0, sticky='w', pady=(4, 0))
        tk.Label(right, textvariable=self.image_note_var, foreground='#8a5').grid(row=2, column=0, sticky='w', pady=(2, 0))

        prompt_frame = tk.LabelFrame(right, text='Prompt - edit this before generating')
        prompt_frame.grid(row=3, column=0, sticky='ew', pady=(10, 10))
        prompt_frame.columnconfigure(0, weight=1)
        self.prompt_text = tk.Text(prompt_frame, height=8, wrap='word')
        self.prompt_text.grid(row=0, column=0, sticky='ew')
        prompt_buttons = tk.Frame(prompt_frame)
        prompt_buttons.grid(row=1, column=0, sticky='w', pady=(6, 0))
        self.prompt_mode_var = tk.StringVar(value='Showing OpenAI prompt')
        tk.Label(prompt_buttons, textvariable=self.prompt_mode_var, foreground='#888').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.openai_prompt_button = tk.Button(prompt_buttons, text='Show OpenAI prompt', command=self.show_openai_prompt)
        self.openai_prompt_button.grid(row=0, column=1, sticky='w', padx=(0, 6))
        self.midjourney_prompt_button = tk.Button(prompt_buttons, text='Show Midjourney prompt', command=self.show_midjourney_prompt)
        self.midjourney_prompt_button.grid(row=0, column=2, sticky='w')

        image_frame = tk.Frame(right)
        image_frame.grid(row=4, column=0, sticky='nsew')
        image_frame.columnconfigure(0, weight=1)
        image_frame.columnconfigure(1, weight=1)
        image_frame.rowconfigure(0, weight=1)

        existing_box = tk.LabelFrame(image_frame, text='Saved image')
        existing_box.grid(row=0, column=0, sticky='nsew', padx=(0, 8))
        existing_box.columnconfigure(0, weight=1)
        existing_box.rowconfigure(0, weight=1)
        self.saved_image_canvas = tk.Canvas(existing_box, bg='#ddd', highlightthickness=0)
        self.saved_image_canvas.grid(row=0, column=0, padx=8, pady=8, sticky='nsew')
        self.saved_image_canvas.bind('<Configure>', self._render_saved_preview)
        self.saved_image_canvas.bind('<Button-1>', lambda _event: self.open_saved_big())
        tk.Button(existing_box, text='View larger', command=self.open_saved_big).grid(row=1, column=0, sticky='ew', padx=8, pady=(0, 8))

        button_row = tk.Frame(right)
        button_row.grid(row=6, column=0, sticky='ew', pady=(10, 0))
        for col in range(10):
            button_row.columnconfigure(col, weight=1)

        batch_frame = tk.Frame(right)
        batch_frame.grid(row=5, column=0, sticky='ew')
        batch_frame.columnconfigure(8, weight=1)
        tk.Label(batch_frame, text='Next unsaved').grid(row=0, column=0, sticky='w')
        self.batch_size_var = tk.StringVar(value='10')
        tk.Entry(batch_frame, textvariable=self.batch_size_var, width=6).grid(row=0, column=1, sticky='w', padx=(6, 12))
        tk.Button(batch_frame, text='Run next unsaved', command=self.run_next_unsaved_batch).grid(row=0, column=2, sticky='w')
        tk.Button(batch_frame, text='Generate 1', command=self.generate_openai).grid(row=0, column=3, sticky='w', padx=(8, 0))
        tk.Label(batch_frame, text='Parallel').grid(row=0, column=4, sticky='w', padx=(12, 4))
        self.batch_parallel_var = tk.StringVar(value=str(self.batch_parallelism))
        tk.Spinbox(
            batch_frame,
            from_=1,
            to=10,
            width=4,
            textvariable=self.batch_parallel_var,
            command=self._on_batch_parallel_change,
        ).grid(row=0, column=5, sticky='w')

        tk.Label(batch_frame, text='Image model').grid(row=1, column=0, sticky='w', pady=(8, 0))
        self.openai_model_var = tk.StringVar(value=self._openai_model_display(self.openai_image_model))
        model_labels = list(self._openai_model_labels())
        self.openai_model_menu = tk.OptionMenu(batch_frame, self.openai_model_var, *model_labels, command=self._on_openai_model_change)
        self.openai_model_menu.grid(row=1, column=1, columnspan=2, sticky='w', padx=(6, 12), pady=(8, 0))
        self.openai_model_hint_var = tk.StringVar(value=self._openai_model_hint(self.openai_image_model))
        tk.Label(batch_frame, textvariable=self.openai_model_hint_var, foreground='#888').grid(
            row=1, column=3, columnspan=6, sticky='w', padx=(12, 0), pady=(8, 0)
        )
        tk.Label(batch_frame, text='Quality').grid(row=2, column=0, sticky='w', pady=(8, 0))
        self.openai_quality_var = tk.StringVar(value=self.openai_image_quality)
        self.openai_quality_menu = tk.OptionMenu(batch_frame, self.openai_quality_var, *OPENAI_IMAGE_QUALITIES, command=self._on_openai_quality_change)
        self.openai_quality_menu.grid(row=2, column=1, columnspan=2, sticky='w', padx=(6, 12), pady=(8, 0))
        self.debug_openai_var = tk.BooleanVar(value=self.debug_openai)
        tk.Checkbutton(
            batch_frame,
            text='Debug OpenAI request/response',
            variable=self.debug_openai_var,
            command=self._on_debug_openai_change,
        ).grid(row=2, column=3, columnspan=3, sticky='w', pady=(8, 0))

        tk.Label(batch_frame, text='Run the next unsaved categories/products, one image per item. They save as awaiting review.', foreground='#888').grid(
            row=3, column=0, columnspan=10, sticky='w', padx=(0, 0), pady=(8, 0)
        )

        tk.Button(button_row, text='Save prompt', command=self.save_prompt).grid(row=0, column=0, sticky='ew', padx=2)
        tk.Button(button_row, text='Use image', command=lambda: self.use_generated(0)).grid(row=0, column=1, sticky='ew', padx=2)
        tk.Button(button_row, text='Attach image...', command=self.attach_existing_image).grid(row=0, column=2, sticky='ew', padx=2)
        tk.Button(button_row, text='Open saved', command=self.open_saved_image).grid(row=0, column=3, sticky='ew', padx=2)
        tk.Button(button_row, text='View larger', command=self.open_saved_big).grid(row=0, column=4, sticky='ew', padx=2)
        tk.Button(button_row, text='Retry current', command=self.retry_current).grid(row=0, column=5, sticky='ew', padx=2)
        tk.Button(button_row, text='Mark reviewed', command=self.mark_reviewed).grid(row=0, column=6, sticky='ew', padx=2)
        tk.Button(button_row, text='Skip', command=self.skip_item).grid(row=0, column=7, sticky='ew', padx=2)
        tk.Button(button_row, text='Next awaiting', command=self.select_first_awaiting_review).grid(row=0, column=8, sticky='ew', padx=2)
        tk.Button(button_row, text='Refresh catalog', command=self.refresh_catalog).grid(row=0, column=9, sticky='ew', padx=2)
        self.footer = tk.StringVar(value='Ready')
        tk.Label(right, textvariable=self.footer, anchor='w').grid(row=7, column=0, sticky='ew', pady=(8, 0))

    def _populate_list(self):
        self.listbox.delete(0, tk.END)
        for item in self.filtered_items:
            marker = 'img' if item_existing_image_path(item) else '   '
            status = item.get('status', '')
            bad_count = int(item.get('openai_bad_responses') or 0)
            bad_label = f' bad response {bad_count}/5' if bad_count else ''
            self.listbox.insert(tk.END, f'{marker} {status:10s} {item_label(item)}{bad_label}')

    def _apply_queue_search(self):
        query = self.search_var.get().strip().lower()
        if not query:
            self.filtered_items = list(self.items)
        else:
            def matches(item):
                haystack = ' '.join(
                    [
                        item_label(item),
                        item.get('type', ''),
                        item.get('status', ''),
                        item.get('route', ''),
                        item.get('title', ''),
                        item.get('parent_title', ''),
                        item.get('category_title', ''),
                    ]
                ).lower()
                return query in haystack

            self.filtered_items = [item for item in self.items if matches(item)]
        self._populate_list()
        if self.filtered_items:
            self.listbox.selection_set(0)
            self.listbox.see(0)
            self.load_item(self.filtered_items[0])
        else:
            self.current_item = None
            self.title_var.set('No item selected')
            self.status_var.set('')
            self.image_note_var.set('No matches')
            self._set_text(self.prompt_text, '')
            self.saved_image_path = None
            self._render_saved_preview()

    def _on_select(self, _event=None):
        selection = self.listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index < len(self.filtered_items):
            self.load_item(self.filtered_items[index])

    def select_first_pending(self):
        for index, item in enumerate(self.filtered_items):
            if item.get('status') == 'pending':
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(index)
                self.listbox.see(index)
                self.load_item(item)
                return
        messagebox.showinfo('Rentalution', 'No pending items found.')

    def load_item(self, item):
        self.current_item = item
        self.title_var.set(item_label(item))
        bad_count = int(item.get('openai_bad_responses') or 0)
        bad_label = f' | bad response {bad_count}/5' if bad_count else ''
        self.status_var.set(f"Route: {item.get('route')} | Status: {item.get('status')}{bad_label}")
        existing_path = item_existing_image_path(item)
        if existing_path:
            self.image_note_var.set(f'Existing image: {existing_path.name}')
        else:
            self.image_note_var.set('Existing image: none')

        self._set_text(self.prompt_text, build_openai_prompt(item))
        self.prompt_mode = 'openai'
        self._update_prompt_buttons()
        self.saved_image_path = existing_path
        self._render_saved_preview()
        self.footer.set('Loaded item')

    def _set_text(self, widget, text):
        widget.delete('1.0', tk.END)
        widget.insert(tk.END, text)

    def _get_prompt_text(self):
        return self.prompt_text.get('1.0', tk.END).strip()

    def save_prompt(self):
        if not self.current_item:
            return
        prompt = self._get_prompt_text()
        if not prompt:
            messagebox.showinfo('Rentalution', 'Prompt is empty.')
            return
        self.current_item['prompt'] = prompt
        save_state(self.state)
        self.footer.set('Saved prompt')

    def _update_prompt_buttons(self):
        if self.prompt_mode == 'openai':
            self.prompt_mode_var.set('Showing OpenAI prompt')
            self.openai_prompt_button.configure(state='disabled')
            self.midjourney_prompt_button.configure(state='normal')
        else:
            self.prompt_mode_var.set('Showing Midjourney prompt')
            self.openai_prompt_button.configure(state='normal')
            self.midjourney_prompt_button.configure(state='disabled')

    def _openai_model_labels(self):
        for name, model in OPENAI_IMAGE_MODELS.items():
            yield f"{model['label']} ({name})"

    def _display_to_model_name(self, display):
        for name, model in OPENAI_IMAGE_MODELS.items():
            if display == f"{model['label']} ({name})":
                return name
        return DEFAULT_OPENAI_IMAGE_MODEL

    def _openai_model_display(self, model_name):
        model = get_openai_image_model(model_name)
        for name, candidate in OPENAI_IMAGE_MODELS.items():
            if candidate == model:
                return f"{candidate['label']} ({name})"
        return f"{model['label']} ({DEFAULT_OPENAI_IMAGE_MODEL})"

    def _openai_model_hint(self, model_name):
        model = get_openai_image_model(model_name)
        return f"Using {model['label']}"

    def _on_debug_openai_change(self):
        self.debug_openai = bool(self.debug_openai_var.get())
        self.state['debug_openai'] = self.debug_openai
        save_state(self.state)

    def _on_batch_parallel_change(self):
        try:
            value = int(self.batch_parallel_var.get())
        except Exception:
            value = 3
        self.batch_parallelism = max(1, min(10, value))
        self.batch_parallel_var.set(str(self.batch_parallelism))
        self.state['batch_parallelism'] = self.batch_parallelism
        save_state(self.state)

    def get_batch_parallelism(self):
        try:
            value = int(self.batch_parallel_var.get())
        except Exception:
            value = self.batch_parallelism
        return max(1, min(10, value))

    def _on_openai_model_change(self, _value=None):
        self.openai_image_model = self._display_to_model_name(self.openai_model_var.get())
        self.openai_model_hint_var.set(self._openai_model_hint(self.openai_image_model))
        self.state['openai_image_model'] = self.openai_image_model
        save_state(self.state)

    def _on_openai_quality_change(self, _value=None):
        self.openai_image_quality = self.openai_quality_var.get()
        self.state['openai_image_quality'] = self.openai_image_quality
        save_state(self.state)

    def _on_debug_openai_change(self):
        self.debug_openai = bool(self.debug_openai_var.get())
        self.state['debug_openai'] = self.debug_openai
        save_state(self.state)

    def _set_label_image(self, label, path, fallback_text, size=THUMB_SIZE):
        if not path:
            label.configure(image='', text=fallback_text)
            return
        image = Image.open(path)
        image = ImageOps.contain(image, size, Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        key = str(path)
        self.preview_refs[key] = photo
        label.configure(image=photo, text='')
        label.image = photo

    def _render_saved_preview(self, _event=None):
        if not hasattr(self, 'saved_image_canvas'):
            return
        canvas = self.saved_image_canvas
        canvas.delete('all')
        path = self.saved_image_path
        if not path and self.current_item:
            path = item_existing_image_path(self.current_item)
        if not path or not Path(path).exists():
            canvas.create_text(
                canvas.winfo_width() // 2,
                canvas.winfo_height() // 2,
                text='No saved image',
                fill='#666',
            )
            self.saved_image_photo = None
            return
        image = Image.open(path)
        max_width = max(1, canvas.winfo_width() - 16)
        max_height = max(1, canvas.winfo_height() - 16)
        image = ImageOps.contain(image, (max_width, max_height), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(image)
        self.saved_image_photo = photo
        canvas.create_image(canvas.winfo_width() // 2, canvas.winfo_height() // 2, image=photo, anchor='center')

    def apply_image_to_item(self, item, selected_path, note_prefix='Uploaded'):
        archived = attach_image_path_to_item(item, selected_path)
        update_item(item, status='uploaded', notes=f'{note_prefix} from {archived.name}')
        save_state(self.state)
        self.saved_image_path = archived
        self._render_saved_preview()
        self._populate_list()
        if item == self.current_item:
            self.load_item(item)
        return archived


    def _run_background(self, fn, on_done):
        self.footer.set('Working...')
        result_box = {'done': False, 'result': None, 'error': None}

        def worker():
            try:
                result_box['result'] = fn()
            except Exception as exc:
                result_box['error'] = exc
            finally:
                result_box['done'] = True

        def poll():
            if not result_box['done']:
                self.root.after(100, poll)
                return
            on_done(result_box['result'], result_box['error'])

        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, poll)

    def _mark_bad_response(self, item, error_text):
        count = int(item.get('openai_bad_responses') or 0) + 1
        item['openai_bad_responses'] = count
        item['openai_last_error'] = error_text
        item['openai_generation_state'] = 'bad response x5' if count >= 5 else f'bad response {count}/5'
        save_state(self.state)
        self._populate_list()
        self.status_var.set(item['openai_generation_state'])
        self.footer.set(item['openai_generation_state'])
        return count

    def _generate_openai_with_retries(self, item, prompt, *, count=1, model=None, quality=None, debug=False, debug_log=None):
        last_error = None
        for _attempt in range(5):
            try:
                return generate_openai_images(
                    prompt,
                    count=count,
                    model=model,
                    quality=quality,
                    debug=debug,
                    debug_log=debug_log,
                )
            except Exception as exc:
                last_error = exc
                self._mark_bad_response(item, str(exc))
        raise last_error

    def generate_openai(self):
        if not self.current_item:
            return
        item = self.current_item
        prompt = self._get_prompt_text() or build_openai_prompt(item)
        self.current_item['prompt'] = prompt
        save_state(self.state)

        def do_generate():
            def log_message(message):
                print(message)
                self.footer.set(message[:180])

            paths = self._generate_openai_with_retries(
                item,
                prompt,
                count=1,
                model=self.openai_image_model,
                quality=self.openai_image_quality,
                debug=self.debug_openai,
                debug_log=log_message,
            )
            return prompt, paths

        def done(result, error):
            if error:
                messagebox.showerror('OpenAI', str(error))
                self.footer.set('bad response x5, skipping')
                self.index += 1
                self.window.after(50, self.process_next)
                return
            prompt_value, paths = result
            self.generated_paths = paths
            self._set_text(self.prompt_text, prompt_value)
            self.footer.set(f'Generated {len(paths)} OpenAI image.')
            if paths:
                self.saved_image_path = paths[0]
                self._render_saved_preview()
            self._show_batch_reviewer(paths)

        self._run_background(do_generate, done)

    def _show_batch_reviewer(self, paths):
        if self.batch_reviewer and self.batch_reviewer.window.winfo_exists():
            self.batch_reviewer.close()
        self.batch_reviewer = BatchReviewer(
            self.root,
            paths,
            on_use=self._use_generated_path,
        )
        self.batch_reviewer.window.lift()
        self.batch_reviewer.window.focus_force()
        self.batch_reviewer.window.attributes('-topmost', True)
        self.root.after(200, lambda: self.batch_reviewer and self.batch_reviewer.window.attributes('-topmost', False))

    def _use_generated_path(self, selected_path):
        if not self.current_item:
            return
        archived = self.apply_image_to_item(self.current_item, selected_path)
        self.footer.set(f'Uploaded {archived.name}')

    def use_generated(self, index):
        if not self.current_item:
            return
        if index >= len(self.generated_paths):
            messagebox.showinfo('Rentalution', 'No generated image at that slot.')
            return
        self._use_generated_path(self.generated_paths[index])

    def next_unsaved_items(self, limit):
        items = []
        for item in self.items:
            if item.get('status') != 'pending':
                continue
            if item_existing_image_path(item):
                continue
            items.append(item)
            if len(items) >= limit:
                break
        return items

    def run_next_unsaved_batch(self):
        try:
            batch_size = int(self.batch_size_var.get().strip())
        except ValueError:
            messagebox.showinfo('Rentalution', 'Batch size must be a whole number.')
            return
        if batch_size < 1:
            messagebox.showinfo('Rentalution', 'Batch size must be at least 1.')
            return

        items = self.next_unsaved_items(batch_size)
        if not items:
            messagebox.showinfo('Rentalution', 'No pending items without a saved image were found.')
            return
        if self.unsaved_batch_runner and self.unsaved_batch_runner.window.winfo_exists():
            self.unsaved_batch_runner.close()
        self.unsaved_batch_runner = UnsavedItemBatchRunner(self, items)
        self.unsaved_batch_runner.window.lift()
        self.unsaved_batch_runner.window.focus_force()

    def select_first_awaiting_review(self):
        for index, item in enumerate(self.items):
            if item.get('status') == 'awaiting_review':
                self.listbox.selection_clear(0, tk.END)
                self.listbox.selection_set(index)
                self.listbox.see(index)
                self.load_item(item)
                return
        messagebox.showinfo('Rentalution', 'No items are waiting for review.')

    def open_saved_image(self):
        if not self.current_item:
            return
        path = item_existing_image_path(self.current_item)
        if not path:
            messagebox.showinfo('Rentalution', 'No saved image for this item.')
            return
        subprocess.Popen(['xdg-open', str(path)])

    def open_saved_big(self):
        if not self.current_item:
            return
        path = item_existing_image_path(self.current_item)
        if not path:
            messagebox.showinfo('Rentalution', 'No saved image for this item.')
            return
        if self.saved_viewer and self.saved_viewer.window.winfo_exists():
            self.saved_viewer.window.lift()
            self.saved_viewer.window.focus_force()
            return
        self.saved_viewer = LargeImageViewer(self.root, path)

    def attach_existing_image(self):
        if not self.current_item:
            return
        selected = filedialog.askopenfilename(
            title='Choose an image to attach',
            initialdir=str(Path.home() / 'Downloads'),
            filetypes=[
                ('Images', '*.png *.jpg *.jpeg *.webp *.gif'),
                ('All files', '*.*'),
            ],
        )
        if not selected:
            return
        source_path = Path(selected)
        if not source_path.exists():
            messagebox.showinfo('Rentalution', 'That file no longer exists.')
            return
        archived = self.apply_image_to_item(self.current_item, source_path, note_prefix='Attached existing image')
        self.footer.set(f'Attached {archived.name}')

    def retry_current(self):
        if not self.current_item:
            return
        prompt = self._get_prompt_text() or build_openai_prompt(self.current_item)
        self.current_item['prompt'] = prompt
        save_state(self.state)

        def do_generate():
            def log_message(message):
                print(message)
                self.footer.set(message[:180])

            paths = self._generate_openai_with_retries(
                self.current_item,
                prompt,
                count=1,
                debug=self.debug_openai,
                debug_log=log_message,
            )
            return prompt, paths

        def done(result, error):
            if error:
                messagebox.showerror('OpenAI', str(error))
                self.footer.set('bad response x5, skipping')
                self.window.after(50, self.process_next)
                return
            _prompt_value, paths = result
            if not paths:
                self.footer.set('Retry returned no images')
                return
            archived = self.apply_image_to_item(self.current_item, paths[0], note_prefix='Retried')
            update_item(self.current_item, status='awaiting_review', notes=f'Retried from {archived.name}')
            save_state(self.state)
            self.footer.set(f'Retried and saved {archived.name}')

        self._run_background(do_generate, done)

    def mark_reviewed(self):
        if not self.current_item:
            return
        update_item(self.current_item, status='reviewed', notes='Reviewed in GUI')
        save_state(self.state)
        self._populate_list()
        self.footer.set('Marked reviewed')

    def show_midjourney_prompt(self):
        if not self.current_item:
            return
        prompt = build_midjourney_prompt(self.current_item)
        self.root.clipboard_clear()
        self.root.clipboard_append(prompt)
        self.root.update()
        self._set_text(self.prompt_text, prompt)
        self.prompt_mode = 'midjourney'
        self._update_prompt_buttons()
        self.footer.set('Midjourney prompt copied to clipboard')

    def show_openai_prompt(self):
        if not self.current_item:
            return
        prompt = build_openai_prompt(self.current_item)
        self.root.clipboard_clear()
        self.root.clipboard_append(prompt)
        self.root.update()
        self._set_text(self.prompt_text, prompt)
        self.prompt_mode = 'openai'
        self._update_prompt_buttons()
        self.footer.set('OpenAI prompt copied to clipboard')

    def skip_item(self):
        if not self.current_item:
            return
        update_item(self.current_item, status='skipped', notes='Skipped from GUI')
        save_state(self.state)
        self._populate_list()
        self.select_first_pending()

    def mark_done(self):
        if not self.current_item:
            return
        update_item(self.current_item, status='done_elsewhere', notes='Handled outside GUI')
        save_state(self.state)
        self._populate_list()
        self.select_first_pending()

    def refresh_catalog(self):
        refresh_state_items(self.state)
        refresh_state_prompts(self.state)
        self.items = self.state['items']
        self._apply_queue_search()
        self._populate_list()
        self.select_first_pending()
        self.footer.set('Catalog refreshed from live database')


class Command(BaseCommand):
    help = 'Launch a simple GUI for the Midjourney/OpenAI image workflow.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Rebuild the workflow queue from the live database.')
        parser.add_argument('--refresh', action='store_true', help='Refresh the saved workflow queue from the live database before opening the GUI.')

    def handle(self, *args, **options):
        state = ensure_state(reset=bool(options.get('reset')))
        if options.get('refresh'):
            refresh_state_items(state)
        if refresh_state_prompts(state):
            print('Refreshed prompts from current database state.')
        root = tk.Tk()
        MidjourneyImageGUI(root, state)
        root.mainloop()
