from flask_assets import Bundle

app_css = Bundle('app.scss', filters='pyscss', output='styles/app.css')

aladin_css = Bundle('aladin.css', output='styles/aladin.css')

default_theme_css = Bundle('default_theme.css', output='styles/default_theme.css')

dark_theme_css = Bundle('dark_theme.css', output='styles/dark_theme.css')

red_theme_css = Bundle('red_theme.css', output='styles/red_theme.css')

app_js = Bundle('app.js', filters='jsmin', output='scripts/app.js')

vendor_css = Bundle('vendor/semantic.min.css', 'vendor/easymde.min.css', output='styles/vendor.css')

vendor_js = Bundle(
    'vendor/jquery.min.js',
    'vendor/semantic.min.js',
    'vendor/tablesort.min.js',
    'vendor/easymde.min.js',
    'vendor/zxcvbn.js',
    # filters='jsmin',
    output='scripts/vendor.js')

aladin_js = Bundle(
    'aladin/aladin.umd.cjs',
    output='scripts/aladin.js'
)

astro_js = Bundle(
    'astro/astroMath.js',
    'astro/projection.js',
    filters='jsmin',
    output='scripts/astro.aggr.js'
)
