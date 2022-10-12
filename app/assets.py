from flask_assets import Bundle

app_css = Bundle('app.scss', filters='pyscss', output='styles/app.css')

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
    'aladin/cds.js',
    'aladin/libs/json2.js',
    'aladin/Logger.js',
    'aladin/libs/jquery.mousewheel.js',
    'aladin/libs/RequestAnimationFrame.js',
    'aladin/libs/Stats.js',
    'aladin/libs/healpix.min.js',
    'aladin/libs/astro/astroMath.js',
    'aladin/libs/astro/projection.js',
    'aladin/libs/astro/coo.js',
    'aladin/SimbadPointer.js',
    'aladin/Box.js',
    'aladin/CooConversion.js',
    'aladin/Sesame.js',
    'aladin/HealpixCache.js',
    'aladin/Utils.js',
    'aladin/URLBuilder.js',
    'aladin/MeasurementTable.js',
    'aladin/Color.js',
    'aladin/AladinUtils.js',
    'aladin/ProjectionEnum.js',
    'aladin/CooFrameEnum.js',
    'aladin/HiPSDefinition.js',
    'aladin/Downloader.js',
    'aladin/libs/fits.js',
    'aladin/MOC.js',
    'aladin/CooGrid.js',
    'aladin/Footprint.js',
    'aladin/Popup.js',
    'aladin/Circle.js',
    'aladin/Polyline.js',
    'aladin/Overlay.js',
    'aladin/Source.js',
    'aladin/Catalog.js',
    'aladin/ProgressiveCat.js',
    'aladin/Tile.js',
    'aladin/TileBuffer.js',
    'aladin/ColorMap.js',
    'aladin/HpxKey.js',
    'aladin/HpxImageSurvey.js',
    'aladin/HealpixGrid.js',
    'aladin/Location.js',
    'aladin/View.js',
    'aladin/Aladin.js',
    filters='jsmin',
    output='scripts/aladin.aggr.js'
)