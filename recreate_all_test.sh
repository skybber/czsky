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

flask recreate_db
flask setup_dev
flask add_test_user
flask add_editor_user
flask add_anonymous_user
flask initialize_catalogues
flask update_dso_axis_ratio
flask add_help_users
flask import_dso_list
flask import_star_list
flask import_double_star_list
flask import_hnsky_supplements
flask import_planets
flask import_planet_moons
flask import_minor_planets
flask import_comets
flask import_supernovae
flask preload_ephemeris
