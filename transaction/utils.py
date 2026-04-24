import random
import string

# TODO work out why migrations breaks when i change this

def random_string_generator(size=10, chars=string.ascii_lowercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

def unique_txn_ref_generator():
    new_txn_ref= random_string_generator()
    qs_exists= Transaction.objects.filter(transaction_reference = new_txn_ref).exists()
    if qs_exists:
        return unique_txn_ref_generator()
    return order_new_id
