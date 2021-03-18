from flask_assets import Bundle

app_css = Bundle('app.scss', filters='scss', output='styles/app.css')

default_theme_css = Bundle('app.scss', filters='scss', output='styles/default_theme.css')

dark_theme_css = Bundle('app.scss', filters='scss', output='styles/dark_theme.css')

red_theme_css = Bundle('app.scss', filters='scss', output='styles/red_theme.css')

app_js = Bundle('app.js', filters='jsmin', output='scripts/app.js')

vendor_css = Bundle('vendor/semantic.min.css', 'vendor/easymde.min.css', output='styles/vendor.css')

vendor_js = Bundle(
    'vendor/jquery.min.js',
    'vendor/semantic.min.js',
    'vendor/tablesort.min.js',
    'vendor/easymde.min.js',
    'vendor/zxcvbn.js',
    filters='jsmin',
    output='scripts/vendor.js')