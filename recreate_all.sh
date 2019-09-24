#!/bin/bash
./manage.py recreate_db
./manage.py setup_dev
./manage.py add_test_user
./manage.py initialize_catalogues
