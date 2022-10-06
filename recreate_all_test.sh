#!/bin/bash

confirm() {
    # call with a prompt string or use a default
    echo "This operation initializes CzSky database. It could be long."
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
./manage.py add_anonymous_user
./manage.py initialize_catalogues
./manage.py update_dso_axis_ratio
./manage.py add_help_users
./manage.py import_dso_list
./manage.py import_star_list
./manage.py import_double_star_list
./manage.py import_minor_planets
./manage.py import_comets
./manage.py import_supernovae
