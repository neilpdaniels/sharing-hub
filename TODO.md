# TODO

- Make the Django test suite deterministic and re-enable `manage.py test` in CI.
  The suite currently calls the live postcodes.io API and has outstanding failures
  and errors. Mock external geocoding, fix the reported tests, then restore the
  CI test step.
