"""
The asset server. All assets are loaded on startup and served from
memory, thus allowing blazing fast serving.
"""

import os
import re
import hashlib
import logging
from importlib import resources

import jinja2
import pscript
import markdown

from . import _utils as utils
from .. import __version__


versionstring = "v" + __version__


logger = logging.getLogger("asgineer")

IMAGE_EXTS = ".png", ".jpg", ".gif", ".ico", ".mp4", ".svg"
FONT_EXTS = ".ttf", ".otf", ".woff", ".woff2"
AUDIO_EXTS = ".wav", ".mp3", ".ogg"

re_fas = re.compile(r"\>(\\uf[0-9a-fA-F][0-9a-fA-F][0-9a-fA-F])\<")

default_template = (
    open(resources.files("timetagger.common") / "_template.html", "rb").read().decode()
)


def _get_base_style():
    fname = resources.files("timetagger.common") / "_style_embed.scss"
    with open(fname, "rb") as f:
        text = f.read().decode()
    return utils.get_scss_vars(text), utils.compile_scss_to_css(text)


style_vars, style_embed = _get_base_style()


def compile_scss(text):
    return utils.compile_scss_to_css(text, **style_vars)


def md2html(text, template):
    title = description = ""
    if text.startswith("%"):
        title, text = text.split("\n", 1)
        title = title.strip("% \t\r\n")
    if text.startswith("%"):
        description, text = text.split("\n", 1)
        description = description.strip("% \t\r\n")
    title = title or "TimeTagger"
    description = description or title
    assert '"' not in description
    # Convert font-awesome codepoints to Unicode chars
    for match in reversed(list(re_fas.finditer(text))):
        text = (
            text[: match.start(1)]
            + eval("'" + match.group(1) + "'")
            + text[match.end(1) :]
        )
    # Some per-line tweaks (turn some headers into anchors, e.g. in support page)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(("## ", "### ")) and "|" in line:
            pre, header = line.split(" ", 1)
            linkname, header = header.split("|", 1)
            pre, linkname, line = pre.strip(), linkname.strip(), header.strip()
            line = f"<a name='{linkname}' href='#{linkname}'>{header}</a>"
            line = f"<h{len(pre)}>{line}</h{len(pre)}>"
            lines[i] = line
    text = "\n".join(lines)
    # Turn md into html and store
    main = markdown.markdown(text, extensions=["fenced_code"])

    if isinstance(template, str):
        template = jinja2.Template(template)
    return template.render(
        title=title,
        description=description,
        main=main,
        embedded_script="",
        embedded_style=style_embed,
        versionstring=versionstring,
    )


def create_assets_from_dir(dirname, template=None):
    """Get a dictionary of assets from a directory."""

    assets = {}

    thtml = default_template
    if template is not None:
        thtml = template
    elif os.path.isfile(os.path.join(dirname, "_template.html")):
        thtml = open(os.path.join(dirname, "_template.html"), "rb").read().decode()
    template = jinja2.Template(thtml)

    for fname in sorted(os.listdir(dirname)):
        if fname.startswith("_"):
            continue
        elif fname.endswith(".md"):
            # Turn markdown into HTML
            text = open(os.path.join(dirname, fname), "rb").read().decode()
            html = md2html(text, template)
            name, ext = os.path.splitext(fname)
            assets["" if name == "index" else name] = html
        elif fname.endswith((".scss", ".sass")):
            # An scss/sass file, a preprocessor of css
            text = open(os.path.join(dirname, fname), "rb").read().decode()
            assets[fname[:-5] + ".css"] = compile_scss(text)
        elif fname.endswith(".html"):
            # Raw HTML
            text = open(os.path.join(dirname, fname), "rb").read().decode()
            assets[fname[:-5]] = text
        elif fname.endswith(".py"):
            # Turn Python into JS
            name, ext = os.path.splitext(fname)
            filename = os.path.join(dirname, fname)
            # Compile
            pycode = open(filename, "rb").read().decode()
            parser = pscript.Parser(pycode, filename)
            jscode = "/* Do not edit, autogenerated by pscript */\n\n" + parser.dump()
            # Wrap in module
            exports = [
                name for name in parser.vars.get_defined() if not name.startswith("_")
            ]
            exports.sort()  # important to produce reproducable assets
            jscode = pscript.create_js_module(name, jscode, [], exports, "simple")
            assets[fname[:-2] + "js"] = jscode.encode()
            logger.info(f"Compiled pscript from {fname}")
        elif fname.endswith((".txt", ".js", ".css", ".json")):
            # Text assets
            assets[fname] = open(os.path.join(dirname, fname), "rb").read().decode()
        elif fname.endswith(IMAGE_EXTS + FONT_EXTS + AUDIO_EXTS):
            # Binary assets
            assets[fname] = open(os.path.join(dirname, fname), "rb").read()
        else:
            continue  # Skip unknown extensions

    logger.info(f"Collected {len(assets)} assets from {dirname}")
    return assets


def enable_service_worker(assets):
    """Enable the service worker 'sw.js', by giving it a cacheName
    based on a hash from all the assets.
    """
    assert "sw.js" in assets, "Expected sw.js in assets"
    sw = assets.pop("sw.js")

    # Generate hash based on content. Use sha1, just like Git does.
    hash = hashlib.sha1()
    for key in sorted(assets.keys()):
        content = assets[key]
        content = content.encode() if isinstance(content, str) else content
        hash.update(content)

    # Generate cache name. The name must start with "timetagger" so
    # that old caches are cleared correctly. We include the version
    # string for clarity. The hash is the most important part. It
    # ensures that the SW is considered new whenever any of the assets
    # change. It also means that two containers serving the same assets
    # use the same hash.
    hash_str = hash.hexdigest()[:12]  # 6 bytes should be more than enough
    cachename = f"timetagger_{versionstring}_{hash_str}"

    # Produce list of assets. If we don't replace this, we get the default SW
    # behavior, which is not doing any caching, essentially being a no-op.
    asset_list = list(sorted(assets.keys()))

    # Update the code
    replacements = {
        "timetagger_cache": cachename,
        "assets = [];": f"assets = {asset_list};",
    }
    for needle, replacement in replacements.items():
        assert needle in sw, f"Expected {needle} in sw.js"
        sw = sw.replace(needle, replacement, 1)
    assets["sw.js"] = sw
