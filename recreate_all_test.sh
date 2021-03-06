#!/bin/bash

confirm() {
    # call with a prompt string or use a default
    echo "This operation recreate DB and initializes catalogues from OpenNGC data. It could be long."
    read -r -p "${1:-Are you sure to recreate all data in DB? [y/N]} " response
    case "$response" in
        [yY][eE][sS]|[yY])
            true
            ;;
        *)
            false
            ;;
    esac
}

! confirm && exit;

./manage.py recreate_db
./manage.py setup_dev
./manage.py add_test_user
./manage.py add_editor_user
./manage.py initialize_catalogues
./manage.py add_help_users
./manage.py import_dso_list
