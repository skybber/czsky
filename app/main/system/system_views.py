import os
import subprocess

from flask import (
    abort,
    Blueprint,
    render_template,
)
from flask_login import current_user, login_required
main_system = Blueprint('main_system', __name__)


@main_system.route('/htop', methods=['GET'])
@login_required
def htop():
    if not current_user.is_monitor():
        abort(404)

    env = os.environ.copy()
    env['TERM'] = env.get('TERM', 'xterm-256color')
    env['COLUMNS'] = env.get('COLUMNS', '220')
    env['LINES'] = env.get('LINES', '60')

    try:
        proc = subprocess.run(
            ["bash", "-lc", "htop -n 1 -F gunicorn | aha --black --line-fix"],
            env=env,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        htop_html = proc.stdout
    except subprocess.TimeoutExpired:
        htop_html = "<pre>Timeout: collecting htop output took too long.</pre>"
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip()
        htop_html = "<pre>Error while running htop/aha."
        if err:
            htop_html += f"\n{err}"
        htop_html += "</pre>"
    except Exception as e:
        htop_html = f"<pre>Unexpected error: {e}</pre>"

    return render_template('main/system/htop.html', htop_output=htop_html)