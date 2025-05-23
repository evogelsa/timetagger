"""
Implementation of HTML-based dialogs.
"""

from pscript import this_is_js
from pscript.stubs import (
    window,
    document,
    console,
    Math,
    isFinite,
    Date,
    Audio,
    Notification,
    isNaN,
)


if this_is_js():
    tools = window.tools
    dt = window.dt
    utils = window.utils
    stores = window.stores

# A stack of dialogs
stack = []


def to_str(x):
    return window.stores.to_str(x)


def show_background_div(show, keep_transparent=False):
    # Create element?
    if not window.dialogbackdiv:
        window.dialogbackdiv = document.createElement("div")
        window.dialogbackdiv.className = "dialog-cover"
        document.getElementById("canvas").parentNode.appendChild(window.dialogbackdiv)
        # Make it block events
        evts = "click", "mousedown", "mousemove", "touchstart", "touchmove"
        for evname in evts:
            window.dialogbackdiv.addEventListener(
                evname, handle_background_div_event, 0
            )
        window.addEventListener("blur", handle_window_blur_event)
        # Block key events (on a div that sits in between dialog and window)
        document.getElementById("main-content").addEventListener(
            "keydown", handle_background_div_event, 0
        )

    if show:
        alpha = 0.0 if keep_transparent else 0.2
        window.dialogbackdiv.style.background = f"rgba(0, 0, 0, {alpha})"
        window.dialogbackdiv.style.pointerEvents = "auto"
        window.dialogbackdiv.style.display = "block"
    else:
        # window.dialogbackdiv.style.display = "none"
        window.dialogbackdiv.style.pointerEvents = "none"
        window.dialogbackdiv.style.background = "rgba(255, 0, 0, 0.0)"


def handle_background_div_event(e):
    if window.dialogbackdiv.style.display == "none":
        return
    e.stopPropagation()
    if e.type == "touchstart":
        e.preventDefault()  # prevent browser sending touch events as a "click" later
    if e.type == "mousedown" or e.type == "touchstart":
        if len(stack) > 0:
            if stack[-1].EXIT_ON_CLICK_OUTSIDE:
                stack[-1].close()


def handle_window_blur_event(e):
    if len(stack) > 0:
        d = stack[-1]
        looks_like_menu = d.TRANSPARENT_BG and d.EXIT_ON_CLICK_OUTSIDE and d.allow_blur
        if looks_like_menu:
            stack[-1].close()


def str_date_to_time_int(d):
    year, month, day = d.split("-")
    return dt.to_time_int(window.Date(int(year), int(month) - 1, int(day)))


def days_ago(t):
    today = dt.floor(dt.now(), "1D")
    the_day = dt.floor(t, "1D")
    return max(0, int((today - the_day) / 86400))


def _browser_history_popstate():
    """When we get into our "first state", we either close the toplevel
    dialog, or go back another step. We also prevent the user from
    navigating with hashes.
    """
    h = window.history
    if h.state and h.state.tt_state:
        if h.state.tt_state == 1:
            if len(stack) > 0:
                h.pushState({"tt_state": 2}, document.title, window.location.pathname)
                stack[-1].close()
            else:
                h.back()
    elif window.location.hash:  # also note the hashchange event
        _consume_browser_hash(window.location.hash)
        h.back()


def _consume_browser_hash(hash):
    """Consume the browser hash. We prevent the hash from being used
    to navigate, but we do allow using the hash to put the app in a
    certain state. For now this only included navogating to a certain
    date.
    """
    d = tools.url2dict(hash)
    if "date" in d:
        t1 = str_date_to_time_int(d.date)
        if not isNaN(t1):
            t2 = dt.add(t1, "1D")
            window.canvas.range.animate_range(t1, t2)


def _browser_history_init():
    """Initialize history. Also take into account that we may come
    here when the user hit back or forward. Basically, we define two
    history states, one with tt_state == 1, and one tt_state == 2. The
    app is nearly always in the latter state. The first is only reached
    briefly when the user presses the back button.
    """

    # In a second or so, we'll consume the current hash
    window.setTimeout(_consume_browser_hash, 1000, window.location.hash)

    # Prep
    h = window.history
    if h.state and h.state.tt_state:
        if h.state.tt_state == 1:
            h.pushState({"tt_state": 2}, document.title, window.location.pathname)
    else:
        h.replaceState({"tt_state": 1}, document.title, window.location.pathname)
        h.pushState({"tt_state": 2}, document.title, window.location.pathname)

    # Now its safe to listen to history changes
    window.addEventListener("popstate", _browser_history_popstate, 0)


_browser_history_init()


def csvsplit(s, sep, i=0):
    """Split a string on the given sep, but take escaping with double-quotes
    into account. Double-quotes themselves can be escaped by duplicating them.
    The resuturned parts are whitespace-trimmed.
    """
    # https://www.iana.org/assignments/media-types/text/tab-separated-values
    # The only case we fail on afaik is tab-seperated values with a value
    # that starts with a quote. Spreadsheets seem not to escape these values.
    # This would make sense if they'd simply never quote TSV as seems to be the
    # "standard", but they *do* use quotes when the value has tabs or newlines :'(
    # In our own exports, we don't allow tabs or newlines, nor quotes at the start,
    # so we should be fine with our own data.
    global RawJS
    parts = []
    RawJS(
        """
    var mode = 0; // 0: between fields, 1: unescaped, 2: escaped
    var sepcode = sep.charCodeAt(0);
    var lastsplit = i;
    i -= 1;
    while (i < s.length - 1) {
        i += 1;
        var cc = s.charCodeAt(i);
        if (mode == 0) {
            if (cc == 34) { // quote
                mode = 2;
            } else if (cc == sepcode) { // empty value
                parts.push("");
                lastsplit = i + 1;
            } else if (cc == 9 || cc == 32 || cc == 13) {
                // ignore whitespace
            } else if (cc == 10) {
                break;  // next line
            } else {
                mode = 1; // unescaped value
            }
        } else if (mode == 1) {
            if (cc == sepcode) {
                parts.push(s.slice(lastsplit, i).trim());
                lastsplit = i + 1;
                mode = 0;
            } else if (cc == 10) {
                mode = 0;
                break;  // next line
            }
        } else { // if (mode == 2)
            if (cc == 34) { // end of escape, unless next char is also a quote
                if (i < s.length - 1 && s.charCodeAt(i + 1) == 34) {
                    i += 1; // Skip over second quote
                } else {
                    mode = 1;
                }
            }
        }
    }
    i += 1;
    parts.push(s.slice(lastsplit, i).trim());
    // Remove escape-quotes
    for (var j=0; j<parts.length; j++) {
        var val = parts[j];
        if (val.length > 0 && val[0] == '"' && val[val.length-1] == '"') {
            parts[j] = val.slice(1, val.length-1).replace('""', '"');
        }
    }
    """
    )
    return parts, i


class BaseDialog:
    """A dialog is widget that is shown as an overlay over the main application.
    Interaction with the application is disabled.
    """

    MODAL = True
    EXIT_ON_CLICK_OUTSIDE = True
    TRANSPARENT_BG = False

    def __init__(self, canvas):
        self._canvas = canvas
        self._create_main_div()
        self._callback = None

    def _create_main_div(self):
        self.maindiv = document.createElement("form")
        self.maindiv.addEventListener("keydown", self._on_key, 0)
        self._canvas.node.parentNode.appendChild(self.maindiv)
        self.maindiv.classList.add("dialog")
        self.maindiv.setAttribute("tabindex", -1)

    def _show_dialog(self):
        self.maindiv.style.display = "block"

        def f():
            self.maindiv.style.opacity = 1

        window.setTimeout(f, 1)

    def _hide_dialog(self):
        self.maindiv.style.display = "none"
        self.maindiv.style.opacity = 0

    def is_shown(self):
        return self.maindiv.style.display == "block"

    def open(self, callback=None):
        self._callback = callback
        self.allow_blur = True
        # Disable main app and any "parent" dialogs
        if self.MODAL:
            show_background_div(True, self.TRANSPARENT_BG)
        if stack:
            stack[-1]._hide_dialog()

        # Show this dialog and add it to the stack
        self._show_dialog()
        stack.append(self)
        self.maindiv.focus()

    def submit_soon(self, *args):
        # Allow focusout and onchanged events to occur
        window.setTimeout(self.submit, 100, *args)

    def submit(self, *args):
        # Close and call back
        callback = self._callback
        self._callback = None
        self.close()
        if callback is not None:
            callback(*args)

    def close(self, e=None):
        """Close/cancel/hide the dialog."""
        # Hide, and remove ourselves from the stack (also if not at the end)
        self._hide_dialog()
        for i in reversed(range(len(stack))):
            if stack[i] is self:
                stack.pop(i)

        # Give conrol back to parent dialog, or to the main app
        if stack:
            stack[-1]._show_dialog()
        for d in stack:
            if d.MODAL:
                show_background_div(True, d.TRANSPARENT_BG)
                break
        else:
            show_background_div(False)
            window.canvas.node.focus()  # See #243

        # Fire callback
        if self._callback is not None:
            self._callback()
            self._callback = None

    def _on_key(self, e):
        if e.key.lower() == "escape":
            self.close()

    def _prevent_blur(self):
        self.allow_blur = False


class DemoInfoDialog(BaseDialog):
    """Dialog to show as the demo starts up."""

    EXIT_ON_CLICK_OUTSIDE = True

    def open(self):
        """Show/open the dialog ."""
        html = """
            <h1>Demo
                <button type='button'><i class='fas'>\uf00d</i></button>
            </h1>
            <p>
            This demo shows 5 years of randomly generated time tracking data.
            Have a look around!
            </p><p>
            <i>Hit Escape or click anywhere outside of this dialog to close it.</i>
            </p>
        """
        self.maindiv.innerHTML = html

        close_but = self.maindiv.children[0].children[-1]
        close_but.onclick = self.close
        super().open(None)


class SandboxInfoDialog(BaseDialog):
    """Dialog to show as the sandbox starts up."""

    EXIT_ON_CLICK_OUTSIDE = True

    def open(self):
        """Show/open the dialog ."""
        html = """
            <h1>Sandbox
                <button type='button'><i class='fas'>\uf00d</i></button>
            </h1>
            <p>
            The TimeTagger sandbox starts without any records. You can play around
            or try importing records. The data is not synced to the server and
            will be lost as soon as you leave this page.
            </p><p>
            <i>Hit Escape or click anywhere outside of this dialog to close it.</i>
            </p>
        """
        self.maindiv.innerHTML = html

        close_but = self.maindiv.children[0].children[-1]
        close_but.onclick = self.close
        super().open(None)


class NotificationDialog(BaseDialog):
    """Dialog to show a message to the user."""

    EXIT_ON_CLICK_OUTSIDE = True

    def open(self, message, title="Notification"):
        """Show/open the dialog ."""
        message
        html = f"""
            <h1>{title}
                <button type='button'><i class='fas'>\uf00d</i></button>
            </h1>
            <p>{message}</p>
        """
        self.maindiv.innerHTML = html
        close_but = self.maindiv.children[0].children[-1]
        close_but.onclick = self.close
        super().open(None)


class MenuDialog(BaseDialog):
    """Dialog to show a popup menu."""

    EXIT_ON_CLICK_OUTSIDE = True
    TRANSPARENT_BG = True

    def open(self):
        """Show/open the dialog ."""

        # Put the menu right next to the menu button
        self.maindiv.style.top = "5px"
        self.maindiv.style.left = "50px"
        self.maindiv.style.maxWidth = "500px"

        self.maindiv.innerHTML = f"""
            <div class='loggedinas'></div>
        """.rstrip()

        # Unpack
        loggedinas = self.maindiv.children[0]

        # Valid store?
        if window.store.get_auth:
            logged_in = store_valid = bool(window.store.get_auth())
        else:
            store_valid = True
            logged_in = False

        is_installable = window.pwa and window.pwa.deferred_prompt

        # Display sensible text in "header"
        if window.store.__name__.startswith("Demo"):
            text = "This is the Demo"
        elif window.store.__name__.startswith("Sandbox"):
            text = "This is the Sandbox"
        elif window.store.get_auth:
            auth = window.store.get_auth()
            if auth:
                text = "Signed in as " + auth.username
            else:
                text = "Not signed in"
        loggedinas.innerText = text

        whatsnew = "What's new"
        whatsnew_url = "https://github.com/almarklein/timetagger/releases"
        if window.timetaggerversion:
            whatsnew += " in version " + window.timetaggerversion.lstrip("v")

        container = self.maindiv
        for icon, show, title, func in [
            (None, True, "External pages", None),
            ("\uf015", True, "Homepage", "/"),
            ("\uf059", True, "Get tips and help", "https://timetagger.app/support"),
            ("\uf0a1", True, whatsnew, whatsnew_url),
            (None, store_valid, "Manage", None),
            ("\uf002", store_valid, "Search", self._search),
            ("\uf56f", store_valid, "Import records", self._import),
            ("\uf56e", store_valid, "Export all records", self._export),
            (None, True, "User", None),
            ("\uf013", store_valid, "Settings", self._show_settings),
            ("\uf2bd", True, "Account", "../account"),
            ("\uf2f6", not logged_in, "Login", "../login"),
            ("\uf2f5", logged_in, "Logout", "../logout"),
            (None, is_installable, None, None),
            ("\uf3fa", is_installable, "<b>Install this app</b>", self._do_install),
        ]:
            if not show:
                continue
            elif not func:
                # Divider
                el = document.createElement("div")
                el.setAttribute("class", "divider")
                if title is not None:
                    el.innerHTML = title
                container.appendChild(el)
            else:
                el = document.createElement("a")
                html = ""
                if icon:
                    html += f"<i class='fas'>{icon}</i>&nbsp;&nbsp;"
                html += title
                el.innerHTML = html
                if isinstance(func, str):
                    el.href = func
                else:
                    el.onclick = func
                container.appendChild(el)

        # more: Settings, User account, inport / export

        self.maindiv.classList.add("verticalmenu")
        super().open(None)

    def _show_settings(self):
        self.close()
        self._canvas.settings_dialog.open()

    def _do_install(self):
        # There are quite a few components to make installation as a
        # PWA possible. In our case:
        # * We have a timetagger_manifest.json
        # * We <link> to it in the template so it can be discovered.
        # * We have a service worker in sw.js, which we activate it in app.md.
        # * In app.md we also do the PWA beforeinstallprompt dance so that in
        #   here we can detect whether it's installable and trigger the install
        self.close()
        window.pwa.install()

    def _open_report(self):
        self.close()
        self._canvas.report_dialog.open()

    def _search(self):
        self.close()
        self._canvas.search_dialog.open()

    def _export(self):
        self.close()
        self._canvas.export_dialog.open()

    def _import(self):
        self.close()
        self._canvas.import_dialog.open()


class TimeSelectionDialog(BaseDialog):
    """Dialog to show a popup for selecting the time range."""

    EXIT_ON_CLICK_OUTSIDE = True
    TRANSPARENT_BG = True

    def open(self, callback=None):
        """Show/open the dialog ."""

        # Transform time int to dates.
        t1, t2 = self._canvas.range.get_target_range()
        t1_date = dt.time2localstr(dt.floor(t1, "1D")).split(" ")[0]
        t2_date = dt.time2localstr(dt.round(t2, "1D")).split(" ")[0]
        if t1_date != t2_date:
            # The date range is inclusive (and we add 1D later): move back one day
            t2_date = dt.time2localstr(dt.add(dt.round(t2, "1D"), "-1D")).split(" ")[0]

        # Generate preamble
        html = f"""
            <div></div>
            <div style='min-height: 6px;'></div>
            <div class='grid5'>
                <a>today</a>
                <a>this week</a>
                <a>this month</a>
                <a>this quarter</a>
                <a>this year</a>
                <a>yester<wbr>day</a>
                <a>last week</a>
                <a>last month</a>
                <a>last quarter</a>
                <a>last year</a>
            </div>
            <div style='min-height: 10px;'></div>
            <div class='menu'>
                <div style='flex: 0.5 0.5 auto; text-align: right;'>From:&nbsp;&nbsp;</div>
                <input type="date" step="1" />
                <div style='flex: 0.5 0.5 auto; text-align: right;'>To:&nbsp;&nbsp;</div>
                <input type="date" step="1" />
                <div style='flex: 0.5 0.5 auto;'></div>
            </div>
            <div style='margin-top:1em;'></div>
            <div style='display: flex;justify-content: flex-end;'>
                <button type='button'>Done</button>
            </div>
        """

        self.maindiv.innerHTML = html
        presets = self.maindiv.children[2]
        form = self.maindiv.children[4]

        self._t1_input = form.children[1]
        self._t2_input = form.children[3]

        # quicknav = self.maindiv.children[0]
        # quicknav.children[1].onclick = lambda e: self._apply_quicknav("out")
        # quicknav.children[2].onclick = lambda e: self._apply_quicknav("in")

        if utils.looks_like_desktop():
            presets.children[0].innerHTML += " <span class='keyhint'>d</span>"
            presets.children[1].innerHTML += " <span class='keyhint'>w</span>"
            presets.children[2].innerHTML += " <span class='keyhint'>m</span>"
            presets.children[3].innerHTML += " <span class='keyhint'>q</span>"
            presets.children[4].innerHTML += " <span class='keyhint'>y</span>"

        for i in range(presets.children.length):
            but = presets.children[i]
            but.onclick = lambda e: self._apply_preset(e.target.innerText)

        self._t1_input.value = t1_date
        self._t1_input.onpointerdown = self._prevent_blur
        self._t1_input.oninput = self._update_range
        self._t2_input.value = t2_date
        self._t2_input.onpointerdown = self._prevent_blur
        self._t2_input.oninput = self._update_range

        close_but = self.maindiv.children[6].children[0]
        close_but.onclick = self.close

        self.maindiv.classList.add("verticalmenu")
        super().open(callback)

    def _apply_quicknav(self, text):
        scalestep = +1 if "out" in text.lower() else -1
        t1, t2 = self._canvas.range.get_snap_range(scalestep)

        self._t1_input.value = dt.time2localstr(t1).split(" ")[0]
        self._t2_input.value = dt.time2localstr(t2).split(" ")[0]

        self._canvas.range.animate_range(t1, t2)

    def _apply_preset(self, text):
        text = text.lower()
        last = text.count("last")
        if text.count("today"):
            rounder = "1D"
        elif text.count("yesterday"):
            rounder = "1D"
            last = True
        elif text.count("week"):
            rounder = "1W"
        elif text.count("month"):
            rounder = "1M"
        elif text.count("quarter"):
            rounder = "3M"
        elif text.count("year"):
            rounder = "1Y"
        else:
            return

        t1 = dt.floor(dt.now(), rounder)
        if last:
            t1 = dt.add(t1, "-" + rounder)
        t2 = dt.add(t1, rounder)
        t2 = dt.add(t2, "-1D")  # range is inclusive

        self._t1_input.value = dt.time2localstr(t1).split(" ")[0]
        self._t2_input.value = dt.time2localstr(t2).split(" ")[0]
        self._update_range()
        self.close()

    def _update_range(self):
        t1_date = self._t1_input.value
        t2_date = self._t2_input.value
        if not float(t1_date.split("-")[0]) > 1899:
            return
        elif not float(t2_date.split("-")[0]) > 1899:
            return

        t1 = str_date_to_time_int(t1_date)
        t2 = str_date_to_time_int(t2_date)
        if t1 > t2:
            t1, t2 = t2, t1
        t2 = dt.add(t2, "1D")  # look until the end of the day

        window.canvas.range.animate_range(t1, t2, None, False)  # without snap


class StartStopEdit:
    """Helper class to allow the user to set the start and stop time of a record."""

    def __init__(self, node, callback, t1, t2, mode):
        self.node = node
        self.callback = callback
        self.initialmode = mode.lower()
        self.initial_t1, self.initial_t2 = t1, t2  # even more original than ori_t1 :)

        if self.initialmode in ("start", "new"):
            text_startnow = "Start now"
            text_startrlr = "Started earlier"
            text_finished = "Already done"
        else:
            text_startnow = "Start now"  # not visible
            text_startrlr = "Still running"
            text_finished = "Stopped"

        self.node.innerHTML = f"""
        <div style='color:#955;'></div>
        <div>
            <label style='user-select:none;'><input type='radio' name='runningornot' />&nbsp;{text_startnow}&nbsp;&nbsp;</label>
            <label style='user-select:none;'><input type='radio' name='runningornot' />&nbsp;{text_startrlr}&nbsp;&nbsp;</label>
            <label style='user-select:none;'><input type='radio' name='runningornot' />&nbsp;{text_finished}&nbsp;&nbsp;</label>
            <div style='min-height:1em;'></div>
        </div>
        <div>
        <span><i class='fas' style='color:#999; vertical-align:middle;'>\uf144</i></span>
            <input type='date' step='1'  style='font-size: 16px;' />
            <span style='display: flex;'>
                <input type='text' style='flex:1; min-width: 50px; font-size: 16px;' />
                <button type='button' style='width:2em; margin-left:-1px;'>+</button>
                <button type='button' style='width:2em; margin-left:-1px;'>-</button>
                </span>
            <span></span>
        <span><i class='fas' style='color:#999; vertical-align:middle;'>\uf28d</i></span>
            <input type='date' step='1' style='font-size: 16px;' />
            <span style='display: flex;'>
                <input type='text' style='flex:1; min-width: 50px; font-size: 16px;' />
                <button type='button' style='width:2em; margin-left:-1px;'>+</button>
                <button type='button' style='width:2em; margin-left:-1px;'>-</button>
                </span>
            <span></span>
        <span><i class='fas' style='color:#999; vertical-align:middle;'>\uf2f2</i></span>
            <span></span>
            <input type='text' style='flex: 1; min-width: 50px; font-size: 16px' />
            <span></span>
        </div>
        """

        # Unpack children
        self.warningnode = self.node.children[0]
        self.radionode = self.node.children[1]
        self.gridnode = self.node.children[2]
        self.radio_startnow = self.radionode.children[0].children[0]
        self.radio_startrlr = self.radionode.children[1].children[0]
        self.radio_finished = self.radionode.children[2].children[0]
        (
            _,  # date and time 1
            self.date1input,
            self.time1stuff,
            _,
            _,  # date and time 2
            self.date2input,
            self.time2stuff,
            _,
            _,  # duration
            _,
            self.durationinput,
            _,
        ) = self.gridnode.children

        self.time1input, self.time1more, self.time1less = self.time1stuff.children
        self.time2input, self.time2more, self.time2less = self.time2stuff.children

        # Tweaks
        for but in (self.time1less, self.time1more, self.time2less, self.time2more):
            but.setAttribute("tabIndex", -1)

        # Styling
        self.gridnode.style.display = "grid"
        self.gridnode.style.gridTemplateColumns = "auto 140px 140px 2fr"
        self.gridnode.style.gridGap = "4px 0.5em"
        self.gridnode.style.justifyItems = "stretch"
        self.gridnode.style.alignItems = "stretch"

        # Set visibility of mode-radio-buttons
        if self.initialmode == "start":
            self.radio_startnow.setAttribute("checked", True)
        elif self.initialmode == "new":
            self.radio_finished.setAttribute("checked", True)
        elif self.initialmode == "stop":
            self.radio_finished.setAttribute("checked", True)
            self.radio_startnow.parentNode.style.display = "none"
        elif t1 == t2:
            self.radio_startrlr.setAttribute("checked", True)
            self.radio_startnow.parentNode.style.display = "none"
        else:
            self.radio_finished.setAttribute("checked", True)
            self.radionode.style.display = "none"

        # Connect events
        self.radio_startnow.onclick = self._on_mode_change
        self.radio_startrlr.onclick = self._on_mode_change
        self.radio_finished.onclick = self._on_mode_change
        self.date1input.onblur = lambda: self.onchanged("date1")
        self.time1input.onchange = lambda: self.onchanged("time1")
        self.date2input.onblur = lambda: self.onchanged("date2")
        self.time2input.onchange = lambda: self.onchanged("time2")
        self.durationinput.onchange = lambda: self.onchanged("duration")
        self.time1more.onclick = lambda: self.onchanged("time1more")
        self.time1less.onclick = lambda: self.onchanged("time1less")
        self.time2more.onclick = lambda: self.onchanged("time2more")
        self.time2less.onclick = lambda: self.onchanged("time2less")
        self.time1input.oninput = lambda: self.onchanged("time1fast")
        self.time2input.oninput = lambda: self.onchanged("time2fast")

        self.reset(t1, t2, True)
        self._timer_handle = window.setInterval(lambda: self._update_duration(), 200)

    def close(self):
        window.clearInterval(self._timer_handle)

    def _get_sensible_start_time(self):
        t2 = dt.now()
        secs_earlier = 8 * 3600  # 8 hours
        running = window.store.records.get_running_records()
        records = window.store.records.get_records(t2 - secs_earlier, t2).values()
        if running:
            t1 = t2 - 300  # 5 min earlier
        elif len(records) > 0:
            records.sort(key=lambda r: r.t2)
            t1 = records[-1].t2  # start time == last records stop time
            t1 = min(t1, t2 - 1)
        else:
            t1 = t2 - 3600  # start time is an hour ago
        return t1

    def _on_mode_change(self):
        if self.initialmode in ("start", "new"):
            t2 = dt.now()
            if self.radio_startnow.checked:
                self.reset(t2, t2)
            else:
                # If the current start time is 5 min earlier, use that, otherwise
                # calculate a sensible start time. The 5 min applies when a sensible
                # start time has already been set, or when the dialog has been
                # on "start now" for over 5 minutes (which is also OK I guess).
                if self.t1 <= t2 - 300:
                    t1 = self.t1
                else:
                    t1 = self._get_sensible_start_time()
                if self.radio_startrlr.checked:
                    self.reset(t1, t1)
                else:
                    self.reset(t1, t2)
        else:
            # Switch between "already running" and "finished".
            # Since this is an existing record, we should maintain initial values.
            if self.radio_startrlr.checked:
                self.reset(self.initial_t1, self.initial_t1)
            else:
                t2 = max(self.initial_t1 + 1, dt.now())
                self.reset(self.initial_t1, t2)

    def reset(self, t1, t2, initial=False):
        """Reset with a given t1 and t2."""

        # Store originals
        self.ori_t1 = self.t1 = t1
        self.ori_t2 = self.t2 = t2

        # Get original dates and (str) times
        self.ori_date1, self.ori_time1 = dt.time2localstr(self.t1).split(" ")
        self.ori_date2, self.ori_time2 = dt.time2localstr(self.t2).split(" ")
        self.ori_days2 = self.days2 = self._days_between_dates(
            self.ori_date1, self.ori_date2
        )

        # Store original str duration
        t = t2 - t1
        self.ori_duration = f"{t//3600:.0f}h {(t//60)%60:02.0f}m {t%60:02.0f}s"

        self._set_time_input_visibility()
        self.render()
        if not initial:
            window.setTimeout(self.callback, 1)

    def _set_time_input_visibility(self):
        def show_subnode(i, show):
            subnode = self.gridnode.children[i]
            if not show:
                subnode.style.display = "none"
            elif i % 4 == 2:
                subnode.style.display = "flex"
            else:
                subnode.style.display = "inline-block"

        for i in range(0, 4):
            show_subnode(i, not self.radio_startnow.checked)
        for i in range(4, 8):
            show_subnode(i, self.radio_finished.checked)
        for i in range(8, 12):
            show_subnode(i, not self.radio_startnow.checked)

    def _update_duration(self, force=False):
        is_running = self.ori_t1 == self.ori_t2
        if not (force or is_running):
            return

        if is_running:
            t = dt.now() - self.t1
            self.durationinput.value = (
                f"{t//3600:.0f}h {(t//60)%60:02.0f}m {t%60:02.0f}s"
            )
        else:
            t = self.t2 - self.t1
            m = Math.round(t / 60)
            self.durationinput.value = f"{m//60:.0f}h {m%60:02.0f}m"

    def _days_between_dates(self, d1, d2):
        year1, month1, day1 = d1.split("-")
        year2, month2, day2 = d2.split("-")
        dt1 = window.Date(year1, month1 - 1, day1).getTime()
        for extraday in range(100):
            dt2 = window.Date(year2, month2 - 1, day2 - extraday).getTime()
            if dt1 == dt2:
                return extraday
        else:
            return 0  # more than 100 days ... fall back to zero?

    def _get_time(self, what, fallback=True):
        node = self[what + "input"]
        hh = mm = ss = None
        if node.value:
            hh, mm, ss = utils.timestr2tuple(node.value)
        if hh is None and fallback:
            if what == "time2":
                self.days2 = self.ori_days2  # rest along with time2
            hh, mm, ss = utils.timestr2tuple(self["ori_" + what])
        return hh, mm, ss

    def _stepwise_delta(self, mm, delta):
        if delta >= 0:
            # delta is positiv, apply modulo with offset
            return delta - (mm % delta)
        else:
            # delta is negative
            mm_new = -(mm % -(delta))
            if mm_new == 0:
                # we are already at stepsize, just return delta
                return delta
            return mm_new

    def render(self):
        now = dt.now()

        # Get date/time info
        t1_date, t1_time = dt.time2localstr(self.t1).split(" ")
        t2_date, t2_time = dt.time2localstr(self.t2).split(" ")
        now_date, now_time = dt.time2localstr(now).split(" ")

        # Set date and time for t1
        self.date1input.value = t1_date
        self.time1input.value = t1_time[:5]
        self.days2 = self._days_between_dates(t1_date, t2_date)

        # Set stop time and duration
        if self.t1 == self.t2:
            # Is running
            t = now - self.t1
            self.time2input.disabled = True
            self.date2input.disabled = True
            self.durationinput.disabled = True
            self.date2input.value = now_date
            self.time2input.value = "running"
            self._update_duration()  # use method that we also use periodically
        else:
            # Is not running
            t = self.t2 - self.t1
            self.time2input.disabled = False
            self.date2input.disabled = False
            self.durationinput.disabled = False
            self.date2input.value = t2_date
            self.time2input.value = t2_time[:5]
            m = Math.round(t / 60)
            self.durationinput.value = f"{m//60:.0f}h {m%60:02.0f}m"

        # Tweak bgcolor of date2 field to hide it a bit
        if self.days2 == 0:
            self.date2input.style.color = "#888"
        else:
            self.date2input.style.color = None

        # Warn about some basic validity checks
        warnings = []
        if "1970" in t1_date:
            warnings.append(f"Invalid date, clipped to 1970")
        elif self.t1 < self.initial_t1 - 86400:
            diff = dt.duration_string(self.initial_t1 - self.t1, False, "dhms")
            warnings.append(f"moving start back {diff}")
        if self.t2 > self.initial_t2 + 86400:
            diff = dt.duration_string(self.t2 - self.initial_t2, False, "dhms")
            warnings.append(f"moving end forward {diff}")
        if self.t2 - self.t1 > 86400:
            diff = dt.duration_string(self.t2 - self.t1, False)
            warnings.append(f"duration is {diff}")
        if warnings:
            self.warningnode.innerHTML = "<i class='fas'>\uf071</i> " + ", ".join(
                warnings
            )
        else:
            self.warningnode.innerHTML = ""

    def onchanged(self, action):
        # step size used for time buttons
        _stepsize = 5

        now = dt.now()

        # Get node
        if (
            action.endsWith("more")
            or action.endsWith("less")
            or action.endswith("fast")
        ):
            what = action[:-4]
            option = action[-4:]
        else:
            what = action
            option = ""
        node = self[what + "input"]
        if not node:
            return

        call_callback = True

        # Get the reference dates
        if self.date1input.value:
            year1, month1, day1 = self.date1input.value.split("-")
        else:
            year1, month1, day1 = self.ori_date1.split("-")
        year1, month1, day1 = int(year1), int(month1), int(day1)
        #
        if self.date2input.value:
            year2, month2, day2 = self.date2input.value.split("-")
        else:
            year2, month2, day2 = self.ori_date2.split("-")
        year2, month2, day2 = int(year2), int(month2), int(day2)

        if what == "date1":
            # Changing date1 -> update both t1 and t2, date2 moves along
            hh, mm, ss = self._get_time("time1")
            d1 = window.Date(year1, month1 - 1, day1, hh, mm, ss)
            hh, mm, ss = self._get_time("time2")
            d2 = window.Date(year1, month1 - 1, day1 + self.days2, hh, mm, ss)
            self.t1 = dt.to_time_int(d1)
            self.t2 = dt.to_time_int(d2)
            if self.ori_t1 == self.ori_t2:
                self.t2 = self.t1
            elif self.t1 >= self.t2:
                self.t2 = self.t1 + 1

        elif what == "date2":
            # Changing date2 -> update only t2
            hh, mm, ss = self._get_time("time2")
            d2 = window.Date(year2, month2 - 1, day2, hh, mm, ss)
            self.t2 = dt.to_time_int(d2)
            if self.ori_t1 == self.ori_t2:
                self.t2 = self.t1
            elif self.t2 <= self.t1:
                self.t2 = self.t1 + 60

        elif what == "time1":
            # Changing time1 -> update t1, keep t2 in check
            if option == "fast":
                hh, mm, ss = self._get_time("time1", False)
                if hh is not None:
                    d1 = window.Date(year1, month1 - 1, day1, hh, mm, ss)
                    self.t1 = dt.to_time_int(d1)
                else:
                    call_callback = False
            else:
                hh, mm, ss = self._get_time("time1")
                if option == "more":
                    mm, ss = mm + self._stepwise_delta(mm, _stepsize), 0
                elif option == "less":
                    mm, ss = mm + self._stepwise_delta(mm, -(_stepsize)), 0
                d1 = window.Date(year1, month1 - 1, day1, hh, mm, ss)
                self.t1 = dt.to_time_int(d1)
                if self.ori_t1 == self.ori_t2:
                    self.t2 = self.t1 = min(self.t1, now)
                elif self.t1 >= self.t2:
                    self.t2 = self.t1 + 1

        elif what == "time2":
            # Changing time2 -> update t2, keep t1 and t2 in check
            if option == "fast":
                hh, mm, ss = self._get_time("time2", False)
                if hh is not None:
                    d2 = window.Date(year2, month2 - 1, day2, hh, mm, ss)
                    self.t2 = dt.to_time_int(d2)
                else:
                    call_callback = False
            else:
                hh, mm, ss = self._get_time("time2")
                if option == "more":
                    mm, ss = mm + self._stepwise_delta(mm, _stepsize), 0
                elif option == "less":
                    mm, ss = mm + self._stepwise_delta(mm, -(_stepsize)), 0
                d2 = window.Date(year2, month2 - 1, day2, hh, mm, ss)
                self.t2 = dt.to_time_int(d2)
                if self.ori_t1 == self.ori_t2:
                    self.t2 = self.t1
                elif self.t2 <= self.t1:
                    self.t1 = self.t2
                    self.t2 = self.t1 + 1

        elif what == "duration":
            # Changing duration -> update t2, but keep it in check
            hh, mm, ss = self._get_time("duration")
            duration = hh * 3600 + mm * 60 + ss
            # Apply
            if self.ori_t1 == self.ori_t2:  # failsafe - keep running
                self.duration = 0
                self.t2 = self.t1
            elif duration < 0:
                self.t1 += duration
                self.t2 = self.t1 + 1
            elif not duration:  # Keep not-running
                self.t2 = self.t1 + 1
            else:
                self.t2 = self.t1 + duration

        # Invoke callback and rerender
        if call_callback:
            window.setTimeout(self.callback, 1)

        if action.endswith("fast"):
            self._update_duration(True)
        else:
            return self.render()


completer_all_tags = None


class Autocompleter:
    """Helper class to autocomplete tags."""

    def __init__(self, div, input, callback, mode_mask=15):
        self._div = div
        self._input = input
        self._callback = callback
        self._mode_mask = mode_mask  # 1: all, 2: tags, 4: presets, 8: descriptions

        self.clear()
        self._state = "", 0, 0

        # Suggested tags
        recent_ds, recent_tags = self._get_suggested_recents()
        self._suggested_ds_recent = recent_ds  # descriptions
        self._suggested_tags_recent = recent_tags
        self._suggested_tags_combined = self._get_suggested_tags_combined()
        self._suggested_tags_presets = []

        # Current suggestion
        self._suggested_tags_in_autocomp = []

        window._autocomp_finish = self._finish_cb

    def close(self):
        self._div = None
        self._input = None
        self._callback = None

    def clear(self):
        self._index = 0
        self._active_suggestion = ""
        if self._div:
            self._div.hidden = True
            self._div.innerHTML = ""
        else:
            pass  # clear can be called when the completer has been closed

    def init(self):
        """Show tag suggestions in the autocompletion dialog."""

        # Get partial tag being written
        self._state = self._get_state()
        val, i1, i2 = self._state
        tag_to_be = val[i1:i2].toLowerCase()

        # Get what to show
        show_descriptions = show_tags = show_presets = False
        if tag_to_be:
            if i1 > 0 and val[i1 - 1] == "#" and (4 & self._mode_mask):
                show_presets = True
            else:
                show_tags = True
            needle = tag_to_be[1:]  # the tag without the '#'
        elif (8 & self._mode_mask) and len(val) >= 2 and " " not in val:
            show_descriptions = True
            needle = val.toLowerCase()
        else:
            self.clear()
            return

        # We show presets if using double hashtags
        if tag_to_be == "#":
            if self._mode_mask == 1:
                return
            elif show_presets:
                return self.show_suggestions("presets")
            else:
                return self.show_suggestions("tags")

        # Obtain suggestions
        matches1 = []  # list of (text, html, select_does_replace)
        matches2 = []  # same
        if show_presets:
            # Suggestions from presets
            for preset in self._get_suggested_tags_presets():
                html = preset + "<span class='meta'>preset<span>"
                i = preset.indexOf(needle)
                if i > 0:
                    if preset[i - 1] == "#":
                        # A tag in the preset startswith the needle
                        html = (
                            preset[: i - 1]
                            + "<b>"
                            + tag_to_be
                            + "</b>"
                            + preset[i + needle.length :]
                        )
                        html += "<span class='meta'>preset<span>"
                        matches1.push((preset, html, False))
                    elif needle.length >= 2:
                        # The preset contains the needle, and the needle is more than 1 char
                        html = (
                            preset[:i]
                            + "<b>"
                            + needle
                            + "</b>"
                            + preset[i + needle.length :]
                        )
                        html += "<span class='meta'>preset<span>"
                        matches2.push((preset, html, False))
        if show_tags:
            # Suggestions from recent tags
            for tag, tag_t2 in self._suggested_tags_combined:
                i = tag.indexOf(needle)
                if i > 0:
                    date = days_ago(tag_t2)
                    date = {0: "today", 1: "yesterday"}.get(date, date + " days ago")
                    if i == 1:
                        # The tag startswith the needle
                        html = "<b>" + tag_to_be + "</b>" + tag[tag_to_be.length :]
                        html += "<span class='meta'>last used " + date + "<span>"
                        matches1.push((tag, html, False))
                    elif needle.length >= 2:
                        # The tag contains the needle, and the needle is more than 1 char
                        html = (
                            tag[:i] + "<b>" + needle + "</b>" + tag[i + needle.length :]
                        )
                        html += "<span class='meta'>last used " + date + "<span>"
                        matches2.push((tag, html, False))
        if show_descriptions:
            # Suggestions from recent descriptions
            for ds, ds_t2 in self._suggested_ds_recent:
                i = ds.toLowerCase().indexOf(needle)
                if i >= 0:
                    date = days_ago(ds_t2)
                    date = {0: "today", 1: "yesterday"}.get(date, date + " days ago")
                    html = (
                        ds[:i]
                        + "<b>"
                        + ds[i : i + needle.length]
                        + "</b>"
                        + ds[i + needle.length :]
                    )
                    html += "<span class='meta'>last used " + date + "<span>"
                    matches2.push((ds, html, True))

        suggestions = matches1
        suggestions.extend(matches2)

        # Show
        if suggestions:
            if show_descriptions:
                self._show("Matching descriptions:", suggestions, False)
            elif show_presets:
                self._show("Matching presets:", suggestions)
            elif self._mode_mask & 2:
                self._show("Matching recent tags:", suggestions)
            else:
                self._show("Matching tags:", suggestions)
        else:
            if show_descriptions:
                self.clear()
            elif show_presets:
                self._show("No matching presets ...", suggestions)
            elif self._mode_mask & 2:
                self._show("No matching recent tags ...", suggestions)
            else:
                self._show("No matching tags ...", suggestions)

    def show_suggestions(self, kind=""):
        suggestions = []
        types = []
        _, words = utils.get_tags_and_parts_from_string(self._input.value)
        search_word = None
        if len(words) == 1:
            search_word = words[0].lower()
        # Collect recent ds's
        if "descriptions" in kind:
            types.push("Recent descriptions")
            if search_word:
                for ds, ds_t2 in self._suggested_ds_recent:
                    if search_word in ds.lower():
                        html = "<b>" + ds + "</b><span class='meta'>match<span>"
                        suggestions.push((ds, html, True))
            for ds, ds_t2 in self._suggested_ds_recent:
                date = days_ago(ds_t2)
                date = {0: "today", 1: "yesterday"}.get(date, date + " days ago")
                html = ds + "<span class='meta'>recent: " + date + "<span>"
                suggestions.push((ds, html, True))
        # Collect presets
        if "presets" in kind:
            types.push("Presets")
            presets = self._get_suggested_tags_presets()
            if search_word:
                for preset in presets:
                    if search_word in preset:
                        html = "<b>" + preset + "</b><span class='meta'>match<span>"
                        suggestions.push((preset, html, True))
            for preset in presets:
                html = preset + "<span class='meta'>preset<span>"
                suggestions.push((preset, html, False))
        # Collect tags
        if "tags" in kind:
            types.push("Recent tags")
            if search_word:
                for tag, tag_t2 in self._suggested_tags_recent:
                    if search_word in tag:
                        html = "<b>" + tag + "</b><span class='meta'>match<span>"
                        suggestions.push((tag, html, True))
            for tag, tag_t2 in self._suggested_tags_recent:
                date = days_ago(tag_t2)
                date = {0: "today", 1: "yesterday"}.get(date, date + " days ago")
                html = tag + "<span class='meta'>recent: " + date + "<span>"
                suggestions.push((tag, html, False))
        # Show
        if not types:
            self.clear()
        elif suggestions:
            self._state = self._get_state()
            self._show(types.join(" & ") + ":", suggestions, False)
        else:
            self._show("No " + types.join(" or ") + " ...", [], False)

    def on_key(self, e):
        if not self._div.hidden:
            key = e.key.lower()
            if key == "enter" or key == "return" or key == "tab":
                self._finish(self._active_suggestion)
                e.preventDefault()
                return True
            elif key == "escape":
                self.clear()
                return True
            elif key == "arrowdown":
                self._make_active(self._index + 1)
                e.preventDefault()
                return True
            elif key == "arrowup":
                self._make_active(self._index - 1)
                e.preventDefault()
                return True
            elif key == "#":
                # Toggle between preset/tags by inserting/removing a '#'
                val, i1, i2 = self._state
                if i2 > i1:
                    is_double = i1 > 0 and val[i1 - 1] == "#"
                    if (self._mode_mask & 4) == 0:
                        if is_double:
                            new_val = val[:i1] + val[i1 + 1 :]
                            new_i = i2 - 1
                        else:
                            new_val = val
                            new_i = i2
                    elif is_double:
                        new_val = val[:i1] + val[i1 + 1 :]
                        new_i = i2 - 1
                    else:
                        new_val = val[:i1] + "#" + val[i1:]
                        new_i = i2 + 1
                    self._input.value = new_val
                    self._input.selectionStart = self._input.selectionEnd = new_i
                    e.preventDefault()
                    self.init()
                    return True

    def has_recent_tags(self):
        return len(self._suggested_tags_recent) > 0

    def _show(self, headline, suggestions, show_toggle=True):
        self.clear()
        # Add title
        hint_html = ""
        if show_toggle and self._mode_mask & 3 and self._mode_mask & 4:
            hint = "(type '#' again to toggle tags / presets)"
            hint_html = "<span style='color:#999;'>" + hint + "</span>"
        item = document.createElement("div")
        item.classList.add("meta")
        item.innerHTML = headline + " &nbsp;&nbsp;&nbsp;" + hint_html
        self._div.appendChild(item)
        # Add suggestions
        self._suggested_tags_in_autocomp = []
        for text, html, select_does_replace in suggestions:  # text is a tag or a preset
            self._suggested_tags_in_autocomp.push((text, select_does_replace))
            i = len(self._suggested_tags_in_autocomp) - 1
            item = document.createElement("div")
            item.classList.add("tag-suggestion")
            item.innerHTML = html
            onclick = f"window._autocomp_finish(event, {i});"
            item.setAttribute("onmousedown", onclick)
            self._div.appendChild(item)
        # Show
        self._div.hidden = False
        self._make_active(0)

    def _make_active(self, index):
        autocomp_count = len(self._suggested_tags_in_autocomp)
        # Correct index (wrap around)
        while index < 0:
            index += autocomp_count
        self._index = index % autocomp_count
        if not autocomp_count:
            return
        # Apply
        self._active_suggestion = self._suggested_tags_in_autocomp[self._index]
        # Fix css class
        for i in range(self._div.children.length):
            self._div.children[i].classList.remove("active")
        child_index = self._index + 1
        active_child = self._div.children[child_index]
        active_child.classList.add("active")
        # Make corresponding item visible
        active_child.scrollIntoView({"block": "nearest"})

    def _finish_cb(self, e, i):
        # Called when the autocomp item is clicked
        self._finish(self._suggested_tags_in_autocomp[i])
        if e and e.stopPropagation:
            e.stopPropagation()
            e.preventDefault()

    def _finish(self, text):
        self.clear()
        if isinstance(text, str):
            text = text
            select_does_replace = False
        else:
            text, select_does_replace = text
        if text:
            if select_does_replace:
                # Recent ds, just replace the whole thing
                self._input.value = text
                self._input.selectionStart = self._input.selectionEnd = len(text)
            else:
                # Append/insert the tag/preset
                # Get pre and post part, in between which we put the new text
                val, i1, i2 = self._state
                pre = val[:i1].rstrip("#").rstrip(" ")
                post = val[i2:].lstrip(" ")
                if pre:
                    pre = pre + " "
                # Compose new value
                self._input.value = pre + text + " " + post
                # Put selection at the end of the inserted text
                cursor_pos = len(pre) + len(text) + 1
                self._input.selectionStart = self._input.selectionEnd = cursor_pos
            if utils.looks_like_desktop():
                self._input.focus()
        self._callback()

    def _get_state(self):
        """Get the partial tag that is being written."""
        # Get value and position
        val = self._input.value
        i2 = self._input.selectionStart
        # If the input element does not have focus, this is all we need
        if window.document.activeElement is not self._input:
            return val, i2, i2
        # Otherwise we try to find the start of the written tag
        i = i2 - 1
        while i >= 0:
            c = val[i]
            if c == "#":
                return val, i, i2
            elif not utils.is_valid_tag_charcode(ord(c)):
                return val, i2, i2
            i -= 1
        return val, i2, i2

    def _get_suggested_tags_presets(self):
        """Get suggested tags based on the presets."""
        item = window.store.settings.get_by_key("tag_presets")
        presets = (None if item is None else item.value) or []
        return [preset for preset in presets if preset]

    def _get_suggested_tags_all_dict(self, force=False):
        """Get *all* tags ever used."""
        PSCRIPT_OVERLOAD = False  # noqa
        global completer_all_tags
        if force or completer_all_tags is None:
            suggested_tags = {}
            for r in window.store.records.get_dump():
                tags, _ = utils.get_tags_and_parts_from_string(r.ds)
                for tag in tags:
                    suggested_tags[tag] = max(r.t2, suggested_tags[tag] | 0)
            completer_all_tags = suggested_tags
        return completer_all_tags

    def _get_suggested_recents(self):
        """Get recent tags and order by their usage/recent-ness."""
        # Get history of somewhat recent records
        t2 = dt.now()
        t1 = t2 - 12 * 7 * 24 * 3600  # 12 weeks, about a quarter year
        records = window.store.records.get_records(t1, t2)
        # Apply Score
        tags_to_scores = {}
        tags_to_t2 = {}
        descriptions = {}
        for r in records.values():
            descriptions[r.ds] = max(r.t2, descriptions[r.ds] | 0)
            tags, _ = utils.get_tags_and_parts_from_string(r.ds)
            score = 1 / (t2 - r.t1)
            for tag in tags:
                tags_to_t2[tag] = max(r.t2, tags_to_t2[tag] | 0)
                tags_to_scores[tag] = (tags_to_scores[tag] | 0) + score
        # Put ds in a list
        ds_list = list(descriptions.items())
        ds_list.sort(key=lambda x: -x[1])
        # Put tags in a list
        score_tag_list = []
        for tag in tags_to_scores.keys():
            if tag == "#untagged":
                continue
            score_tag_list.push((tag, tags_to_t2[tag], tags_to_scores[tag]))
        # Sort by score and trim names
        score_tag_list.sort(key=lambda x: -x[2])
        tag_list = [score_tag[:2] for score_tag in score_tag_list]
        return ds_list, tag_list

    def _get_suggested_tags_combined(self):
        """Combine the full tag dict with the more recent tags."""
        # Collect
        tags_dict = {}
        new_tags = []
        if self._mode_mask & 1:
            tags_dict = self._get_suggested_tags_all_dict(self._mode_mask == 1).copy()
        if self._mode_mask & 2:
            new_tags = self._suggested_tags_recent
        # Combine
        for tag, tag_t2 in new_tags:
            tags_dict[tag] = tag_t2
        # Compose full tag suggestions list
        tag_list = []
        for tag, tag_t2 in tags_dict.items():
            tag_list.push((tag, tag_t2))
        tag_list.sort(key=lambda x: x[0])
        return tag_list


class RecordDialog(BaseDialog):
    """Dialog to allow modifying a record (setting description and times)."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self._record = None
        self._no_user_edit_yet = True

        # Enable stopping a record via the notification
        if window.navigator.serviceWorker:
            try:
                window.navigator.serviceWorker.addEventListener(
                    "message", self.on_notificationclick
                )
            except Exception:
                pass

    def open(self, mode, record, callback=None):
        """Show/open the dialog for the given record. On submit, the
        record will be pushed to the store and callback (if given) will
        be called with the record. On close/cancel, the callback will
        be called without arguments.
        """
        self._record = record.copy()
        assert mode.lower() in ("start", "new", "edit", "stop")

        html = f"""
            <h1><i class='fas'>\uf682</i>&nbsp;&nbsp;<span>Record</span>
                <button type='button'><i class='fas'>\uf00d</i></button>
            </h1>
            <h2><i class='fas'>\uf305</i>&nbsp;&nbsp;Description</h2>
            <div class='container' style='position: relative;'>
                <input type='text' style='width:100%;' spellcheck='true' />
                <div class='tag-suggestions-autocomp'></div>
            </div>
            <div class='container' style='min-height:20px;'>
                <button type='button' style='float:right; font-size:75%; margin-top:-4px;'>
                    <i class='fas'>\uf044</i></button>
                <button type='button' style='float:right; font-size:75%; margin-top:-4px;'>
                    Presets <i class='fas'>\uf0d7</i></button>
                <button type='button' style='float:right; font-size:75%; margin-top:-4px;'>
                    Tags <i class='fas'>\uf0d7</i></button>
                <button type='button' style='float:right; font-size:75%; margin-top:-4px;'>
                    Recent <i class='fas'>\uf0d7</i></button>
            </div>
            <div></div>
            <div style='color:#777;'></div>
            <h2><i class='fas'>\uf017</i>&nbsp;&nbsp;Time</h2>
            <div></div>
            <div style='margin-top:2em;'></div>
            <div style='display: flex;justify-content: flex-end;'>
                <button type='button' class='actionbutton'><i class='fas'>\uf00d</i>&nbsp;&nbsp;Cancel</button>
                <button type='button' class='actionbutton'><i class='fas'>\uf1f8</i>&nbsp;&nbsp;Delete</button>
                <button type='button' class='actionbutton'><i class='fas'>\uf24d</i>&nbsp;&nbsp;Resume</button>
                <button type='button' class='actionbutton submit'>Submit</button>
            </div>
            <button type='button' style='float:right;' class='actionbutton'>Confirm deleting this record</button>
        """
        self.maindiv.innerHTML = html

        # Unpack so we have all the components
        (
            h1,  # Dialog title
            self._ds_header,
            self._ds_container,
            self._preset_container,
            self._tags_div,
            self._tag_hints_div,
            _,  # Time header
            self._time_node,
            _,  # Splitter
            self._buttons,
            self._delete_but2,
        ) = self.maindiv.children
        #
        self._ds_input = self._ds_container.children[0]
        self._autocompleter_div = self._ds_container.children[1]
        self._recent_but = self._preset_container.children[3]
        self._tags_but = self._preset_container.children[2]
        self._preset_but = self._preset_container.children[1]
        self._preset_edit = self._preset_container.children[0]
        self._title_div = h1.children[1]
        self._cancel_but1 = self.maindiv.children[0].children[-1]
        (
            self._cancel_but2,
            self._delete_but1,
            self._resume_but,
            self._submit_but,
        ) = self._buttons.children

        # Create the startstop-edit
        self._time_edit = StartStopEdit(
            self._time_node, self._on_times_change, record.t1, record.t2, mode
        )

        # Prepare autocompletion
        self._autocompleter = Autocompleter(
            self._autocompleter_div, self._ds_input, self._autocomp_finished
        )

        # Set some initial values
        self._ds_input.value = record.get("ds", "")
        self._show_tags_from_ds()
        self._delete_but2.style.display = "none"
        self._no_user_edit_yet = True

        # Show the right buttons
        self._set_mode(mode)

        # Connect things up
        self._cancel_but1.onclick = self.close
        self._cancel_but2.onclick = self.close
        self._submit_but.onclick = self.submit_soon
        self._resume_but.onclick = self.resume_record
        self._ds_input.oninput = self._on_user_edit
        self._ds_input.onblur = self._on_user_edit_done
        self._recent_but.onclick = self.show_recent_descriptions
        self._tags_but.onclick = self.show_recent_tags
        self._preset_but.onclick = self.show_presets
        self._preset_edit.onclick = lambda: self._canvas.tag_preset_dialog.open()
        self._delete_but1.onclick = self._delete1
        self._delete_but2.onclick = self._delete2
        self.maindiv.addEventListener("click", self._autocompleter.clear)

        # Generate the next random tag color
        color = utils.color_random()
        window.simplesettings.set("next_random_color", color)

        # Enable for some more info (e.g. during dev)
        if False:
            for x in [f"ID: {record.key}", f"Modified: {dt.time2localstr(record.mt)}"]:
                el = document.createElement("div")
                el.innerText = x
                self.maindiv.appendChild(el)

        # Almost done. Focus on ds if this looks like desktop; it's anoying on mobile
        super().open(callback)
        if utils.looks_like_desktop():
            self._ds_input.focus()

    def _autocomp_finished(self):
        self._show_tags_from_ds()
        self._mark_as_edited()

    def _set_mode(self, mode):
        self._lmode = lmode = mode.lower()
        self._title_div.innerText = f"{mode} record"
        is_running = self._record.t1 == self._record.t2
        # has_running = len(window.store.records.get_running_records()) > 0
        # Set description placeholder
        if lmode == "start":
            self._ds_input.setAttribute("placeholder", "What are you going to do?")
        elif lmode == "new":
            self._ds_input.setAttribute("placeholder", "What have you done?")
        elif lmode == "stop":
            self._ds_input.setAttribute("placeholder", "What did you just do?")
        elif is_running:
            self._ds_input.setAttribute("placeholder", "What are you doing?")
        else:
            self._ds_input.setAttribute("placeholder", "What has been done?")
        # Tweak the buttons at the bottom
        if lmode == "start":
            self._submit_but.innerHTML = "<i class='fas'>\uf04b</i>&nbsp;&nbsp;Start"
            self._resume_but.style.display = "none"
            self._delete_but1.style.display = "none"
        elif lmode == "new":
            self._submit_but.innerHTML = "<i class='fas'>\uf067</i>&nbsp;&nbsp;Create"
            self._resume_but.style.display = "none"
            self._delete_but1.style.display = "none"
        elif lmode == "edit":
            self._submit_but.innerHTML = "<i class='fas'>\uf304</i>&nbsp;&nbsp;Save"
            title_mode = "Edit running" if is_running else "Edit"
            self._title_div.innerText = f"{title_mode} record"
            self._submit_but.disabled = self._no_user_edit_yet
            self._resume_but.style.display = "none" if is_running else "block"
            self._delete_but1.style.display = "block"
        elif lmode == "stop":
            self._submit_but.innerHTML = "<i class='fas'>\uf04d</i>&nbsp;&nbsp;Save"
            self._resume_but.style.display = "none"
            self._delete_but1.style.display = "block"
        else:
            console.warn("Unexpected record dialog mode " + mode)

    def _mark_as_edited(self):
        if self._no_user_edit_yet:
            self._no_user_edit_yet = False
            self._submit_but.disabled = False

    def _on_user_edit(self):
        self._mark_as_edited()
        self._autocompleter.init()
        self._show_tags_from_ds()
        # If the str is too long, limit it
        if len(self._ds_input.value) >= stores.STR_MAX:
            self._ds_input.value = self._ds_input.value.slice(0, stores.STR_MAX)
            if "max" not in self._ds_header.innerHTML:
                self._ds_header.innerHTML += (
                    f" <small>(max {stores.STR_MAX-1} chars)</small>"
                )
            self._ds_input.style.setProperty("outline", "dashed 2px red")
            reset = lambda: self._ds_input.style.setProperty("outline", "")
            window.setTimeout(reset, 2000)

    def show_presets(self, e):
        # Prevent that the click will hide the autocomp
        if e and e.stopPropagation:
            e.stopPropagation()
        self._autocompleter.show_suggestions("presets")
        # Note: don't give ds_input focus, because that will pop up the
        # keyboard on mobile devices

    def show_recent_tags(self, e):
        # Prevent that the click will hide the autocomp
        if e and e.stopPropagation:
            e.stopPropagation()
        self._autocompleter.show_suggestions("tags")

    def show_recent_descriptions(self, e):
        if e and e.stopPropagation:
            e.stopPropagation()
        self._autocompleter.show_suggestions("descriptions")

    def _add_tag(self, tag):
        self._ds_input.value = self._ds_input.value.rstrip() + " " + tag + " "
        self._on_user_edit()
        if utils.looks_like_desktop():
            self._ds_input.focus()

    def _on_user_edit_done(self):
        self._autocompleter.clear()
        ds = to_str(self._ds_input.value)
        _, parts = utils.get_tags_and_parts_from_string(ds)
        self._ds_input.value = parts.join("").strip()
        self._show_tags_from_ds()

    def _on_times_change(self):
        was_running = self._record.t1 == self._record.t2
        self._record.t1 = self._time_edit.t1
        self._record.t2 = self._time_edit.t2
        is_running = self._record.t1 == self._record.t2

        self._mark_as_edited()
        # Swap mode?
        if was_running and not is_running:
            if self._lmode == "start":
                self._set_mode("New")
            else:
                self._set_mode("Stop")
        elif is_running and not was_running:
            if self._lmode == "new":
                self._set_mode("Start")
            else:
                self._set_mode("Edit")

    def _show_tags_from_ds(self):
        """Get all current tags. If different, update suggestions."""
        # Show info about current tags in description
        tags, parts = utils.get_tags_and_parts_from_string(self._ds_input.value)
        tags_html = "Tags:&nbsp; &nbsp;"
        if len(tags) == 0:
            tags = ["#untagged"]
        tags_list = []
        for tag in tags:
            clr = window.store.settings.get_color_for_tag(tag)
            tags_list.append(f"<b style='color:{clr};'>#</b>{tag[1:]}")
        tags_html += "&nbsp; &nbsp;".join(tags_list)
        # Get hints
        hint_html = ""
        if not self._autocompleter.has_recent_tags():
            hint_html = "Use e.g. '&#35;meeting' to add one or more tags."
        # Detect duplicate tags
        tag_counts = {}
        for part in parts:
            if part.startswith("#"):
                tag_counts[part] = tag_counts.get(part, 0) + 1
        duplicates = [tag for tag, count in tag_counts.items() if count > 1]
        if len(duplicates):
            hint_html += "<br>Duplicate tags: " + duplicates.join(" ")
        # Detect URL's
        urls = []
        for part in parts:
            for word in part.split():
                if word.startsWith("http://") or word.startsWith("https://"):
                    urls.append(word.strip("'").strip('"'))
        if urls:
            hint_html += "<br>Links:"
            for url in urls:
                hint_html += f"<br><a style='font-size:smaller;' href='{url}' target='_blank'>{url}</a>"
        # Apply
        self._tag_hints_div.innerHTML = hint_html
        self._tags_div.innerHTML = tags_html

    def close(self, e=None):
        self._time_edit.close()
        self._autocompleter.close()
        super().close(e)

    def _on_key(self, e):
        key = e.key.lower()
        if self._autocompleter.on_key(e):
            e.stopPropagation()
            return
        elif key == "enter" or key == "return":
            self.submit_soon()
        else:
            super()._on_key(e)

    def _delete1(self):
        self._delete_but2.style.display = "block"

    def _delete2(self):
        record = self._record
        window.stores.make_hidden(record)  # Sets the description
        record.t2 = record.t1 + 1  # Set duration to 1s (t1 == t2 means running)
        window.store.records.put(record)
        self.close(record)

    def _stop_all_running_records(self, t2=None):
        records = window.store.records.get_running_records()
        if t2 is None:
            t2 = dt.now()
        for record in records:
            record.t2 = max(record.t1 + 2, t2)
            window.store.records.put(record)

    def submit(self):
        """Submit the record to the store."""
        # Submit means close if there was nothing to submit
        if self._submit_but.disabled:
            return self.close()
        # Set record.ds
        _, parts = utils.get_tags_and_parts_from_string(to_str(self._ds_input.value))
        self._record.ds = parts.join("")
        if not self._record.ds:
            self._record.pop("ds", None)
        # Prevent multiple timers at once
        if self._record.t1 == self._record.t2:
            self._stop_all_running_records(self._record.t1)
        # Apply
        window.store.records.put(self._record)
        super().submit(self._record)
        # Notify
        if self._lmode == "start":
            self.send_notification(self._record)
        # Start pomo?
        if window.simplesettings.get("pomodoro_enabled"):
            if self._lmode == "start":
                self._canvas.pomodoro_dialog.start_work()
            elif self._lmode == "stop":
                self._canvas.pomodoro_dialog.stop()

    def resume_record(self):
        """Start a new record with the same description."""
        # The resume button should only be visible for non-running records, but
        # if (for whatever reason) this gets called, resume will mean leave running.
        if self._record.t1 == self._record.t2:
            return self.submit()
        # In case other timers are runnning, stop these!
        self._stop_all_running_records()
        # Create new record with current description
        now = dt.now()
        record = window.store.records.create(now, now)
        _, parts = utils.get_tags_and_parts_from_string(to_str(self._ds_input.value))
        record.ds = parts.join("")
        window.store.records.put(record)
        # Close the dialog - don't apply local changes
        self.close()
        # Move to today, if needed
        t1, t2 = self._canvas.range.get_target_range()
        if not (t1 < now < t2):
            t1, t2 = self._canvas.range.get_today_range()
            self._canvas.range.animate_range(t1, t2)
        # Notify
        self.send_notification(record)
        # Start pomo?
        if window.simplesettings.get("pomodoro_enabled"):
            self._canvas.pomodoro_dialog.start_work()

    def send_notification(self, record):
        if not window.simplesettings.get("notifications"):
            return
        if window.Notification and Notification.permission != "granted":
            return

        title = "TimeTagger is tracking time"
        actions = [
            {"action": "stop", "title": "Stop"},
        ]
        options = {
            "icon": "timetagger192_sf.png",
            "body": record.ds or "",
            "requireInteraction": True,
            "tag": "timetagger-running",  # replace previous notifications
        }
        # If we show the notification via the service worker, we
        # can show actions, making the flow easier for users.
        if window.pwa and window.pwa.sw_reg:
            options.actions = actions
            window.pwa.sw_reg.showNotification(title, options)
        else:
            Notification(title, options)

    def on_notificationclick(self, message_event):
        event = message_event.data
        if event.type != "notificationclick":
            return
        if event.action == "stop":
            self._stop_all_running_records()


class TargetHelper:
    """A little class to help with targets. Because targets occur in two dialogs."""

    def __init__(self, tagz, div):
        self._tagz = tagz

        div.innerHTML = f"""
            <input type='number' min=1 value=1 style='width:5em;' />
            <span style='padding: 0 1em;'>hours per</span>
            <select>
                <option value='none'>No target</option>
                <option value='day'>Day</option>
                <option value='week'>Week</option>
                <option value='month'>Month</option>
                <option value='year'>Year</option>
            </select>
            """

        self._hour_input, _, self._period_select = div.children

    def load_from_info(self, info):
        targets = info.get("targets", None) or {}
        for period, hours in targets.items():
            if period and hours:
                self._hour_input.value = hours or 1
                self._period_select.value = period or "none"
                break
            else:
                self._hour_input.value = 0
                self._period_select.value = "none"

    def write_to_info(self, info):
        targets = {}

        hours = float(self._hour_input.value)
        period = self._period_select.value
        if hours > 0 and period and period != "none":
            targets[period] = hours

        info.targets = targets


class TagComboDialog(BaseDialog):
    """Dialog to configure a combination of tags."""

    def open(self, tags, callback):
        # Put in deterministic order
        if isinstance(tags, str):
            tags = tags.split(" ")
        tags.sort()
        self._tagz = tagz = tags.join(" ")

        self.maindiv.innerHTML = f"""
            <h1><i class='fas'>\uf02c</i>&nbsp;&nbsp;Tag combo {tagz}
                <button type='button'><i class='fas'>\uf00d</i></button>
                </h1>
            <h2><i class='fas'>\uf02c</i>&nbsp;&nbsp;Tags</h2>
            <div>buttons for tags go here</div>
            <h2><i class='fas'>\uf140</i>&nbsp;&nbsp;Target</h2>
            <div>target goes here</div>
            <div style='margin-top:2em;'></div>
            <div style='display: flex;justify-content: flex-end;'>
                <button type='button' class='actionbutton'><i class='fas'>\uf304</i>&nbsp;&nbsp;Rename</button>
                <button type='button' class='actionbutton'><i class='fas'>\uf00d</i>&nbsp;&nbsp;Cancel</button>
                <button type='button' class='actionbutton submit'><i class='fas'>\uf00c</i>&nbsp;&nbsp;Apply</button>
            </div>
        """

        close_but = self.maindiv.children[0].children[-1]
        (
            _,
            _,  # button header
            button_div,
            _,  # target header
            target_div,
            _,  # margin
            finish_buttons,
        ) = self.maindiv.children
        close_but.onclick = self.close

        button_div.innerHTML = ""
        for tag in tags:
            clr = window.store.settings.get_color_for_tag(tag)
            el = document.createElement("button")
            el.setAttribute("type", "button")
            el.style.marginRight = "3px"
            el.innerHTML = f"<b style='color:{clr};'>#</b>" + tag[1:]
            el.onclick = self._make_click_handler(tag, callback)
            button_div.appendChild(el)

        self._target = TargetHelper(tags, target_div)
        finish_buttons.children[0].onclick = self.rename
        finish_buttons.children[1].onclick = self.close
        finish_buttons.children[2].onclick = self.submit

        super().open(None)
        self._load_current()

    def _make_click_handler(self, tag, callback):
        def handler():
            self.close()
            self._canvas.tag_dialog.open(tag, callback),

        return handler

    def _load_current(self):
        info = window.store.settings.get_tag_info(self._tagz)
        self._target.load_from_info(info)

    def submit(self):
        info = {}
        self._target.write_to_info(info)
        window.store.settings.set_tag_info(self._tagz, info)
        super().submit()

    def rename(self):
        self._canvas.tag_rename_dialog.open(self._tagz.split(" "), self.close)


class TagDialog(BaseDialog):
    """Dialog to configure a singleton tag."""

    def open(self, tags, callback=None):
        # Put in deterministic order
        if isinstance(tags, str):
            tags = tags.split(" ")
        tags.sort()
        self._tagz = tagz = tags.join(" ")

        self._default_color = window.front.COLORS.acc_clr
        # self._default_color = utils.color_from_name(self._tagz)

        self.maindiv.innerHTML = f"""
            <h1><i class='fas'>\uf02b</i>&nbsp;&nbsp;Configure tag {tagz}
                <button type='button'><i class='fas'>\uf00d</i></button>
                </h1>
            <h2><i class='fas'>\uf140</i>&nbsp;&nbsp;Target</h2>
            <div>target goes here</div>
            <h2><i class='fas'>\uf074</i>&nbsp;&nbsp;Priority</h2>
            <select>
                <option value='1'>Primary (default)</option>
                <option value='2'>Secondary (for "extra" tags)</option>
            </select>
            <h2><i class='fas'>\uf53f</i>&nbsp;&nbsp;Color</h2>
            <input type='text' style='width: 100px; border: 5px solid #eee' spellcheck='false' />
            <button type='button' style='margin-left: 2px'><i class='fas'>\uf12d</i> Default</button>
            <button type='button' style='margin-left: 2px'><i class='fas'>\uf2f1</i> Random</button>
            <br>
            <div style='display: inline-grid; grid-gap: 2px;'></div>
            <div style='margin-top:2em;'></div>
            <div style='display: flex;justify-content: flex-end;'>
                <button type='button' class='actionbutton'><i class='fas'>\uf304</i>&nbsp;&nbsp;Rename</button>
                <button type='button' class='actionbutton'><i class='fas'>\uf00d</i>&nbsp;&nbsp;Cancel</button>
                <button type='button' class='actionbutton submit'><i class='fas'>\uf00c</i>&nbsp;&nbsp;Apply</button>
            </div>
        """

        close_but = self.maindiv.children[0].children[-1]

        (
            _,  # h1
            _,  # target header
            target_div,
            _,  # priority header
            self._priority_select,
            _,  # color header
            self._color_input,
            self._color_default_button,
            self._color_random_button,
            _,  # br
            self._color_grid,
            _,  # gap
            finish_buttons,
        ) = self.maindiv.children

        self._target = TargetHelper(tags, target_div)

        # Connect things up
        close_but.onclick = self.close
        finish_buttons.children[0].onclick = self.rename
        finish_buttons.children[1].onclick = self.close
        finish_buttons.children[2].onclick = self.submit

        self._color_input.onchange = lambda: self._set_color(self._color_input.value)
        self._color_default_button.onclick = self._set_default_color
        self._color_random_button.onclick = self._set_random_color

        # Generate palette
        self._color_grid.style.gridTemplateColumns = "auto ".repeat(utils.PALETTE_COLS)
        for hex in utils.PALETTE2:
            el = document.createElement("span")
            el.style.background = hex
            el.style.width = "30px"
            el.style.height = "30px"
            self._make_clickable(el, hex)
            self._color_grid.appendChild(el)

        super().open(callback)
        self._load_current()
        if utils.looks_like_desktop():
            self._color_input.focus()
            self._color_input.select()

    def _on_key(self, e):
        key = e.key.lower()
        if key == "enter" or key == "return":
            e.preventDefault()
            self.submit()
        else:
            super()._on_key(e)

    def _make_clickable(self, el, hex):
        # def clickcallback():
        #     self._color_input.value = hex
        el.onclick = lambda: self._set_color(hex)

    def _set_default_color(self):
        self._set_color(self._default_color)

    def _set_random_color(self):
        clr = utils.color_random()
        self._set_color(clr)

    def _set_color(self, clr):
        if not clr or clr.lower() in ["auto", "undefined", "null"]:
            clr = self._default_color
        if clr != self._color_input.value:
            self._color_input.value = clr
        self._color_input.style.borderColor = "rgba(0, 0, 0, 0)"
        self._color_input.style.borderColor = clr

    def _load_current(self):
        info = window.store.settings.get_tag_info(self._tagz)
        self._target.load_from_info(info)
        self._priority_select.value = info.get("priority", 0) or 1
        self._set_color(info.get("color", ""))

    def submit(self):
        info = {}
        # Set target
        self._target.write_to_info(info)
        # Set priority
        prio = int(self._priority_select.value)
        info["priority"] = 0 if prio == 1 else prio
        # Set color
        clr = self._color_input.value
        info["color"] = "" if clr == self._default_color else clr
        # Store
        window.store.settings.set_tag_info(self._tagz, info)
        super().submit()

    def rename(self):
        self._canvas.tag_rename_dialog.open(self._tagz.split(" "), self.close)


class TagPresetsDialog(BaseDialog):
    """Dialog to define tag presets."""

    def open(self, callback=None):
        self.maindiv.innerHTML = f"""
            <h1><i class='fas'>\uf044</i>&nbsp;&nbsp;Tag presets
                <button type='button'><i class='fas'>\uf00d</i></button>
            </h1>
            <p>
            Use the text field below to define tag presets, one per line.
            Each line may contain one or more tags.
            You can also drag-and-drop a text file with presets.
            </p>
            <button type='button'>Check & Save</button>
            <div></div>
            <textarea rows='12'
                style='background: #fff; display: block; margin: 0.5em; width: calc(100% - 1.5em);'>
            </textarea>
            """

        self._input_element = self.maindiv.children[-1]
        self._input_element.value = ""
        self._input_element.ondragexit = self._on_drop_stop
        self._input_element.ondragover = self._on_drop_over
        self._input_element.ondrop = self._on_drop
        self._input_element.oninput = self._on_edit
        self._input_element.onchange = self._on_edit

        self._analysis_out = self.maindiv.children[-2]

        self._apply_but = self.maindiv.children[2]
        self._apply_but.onclick = self.do_apply

        self._cancel_but = self.maindiv.children[0].children[-1]
        self._cancel_but.onclick = self.close
        super().open(callback)
        self._load_current()

    def _on_drop_stop(self, ev):
        self._input_element.style.background = None

    def _on_drop_over(self, ev):
        ev.preventDefault()
        self._input_element.style.background = "#DFD"

    def _on_drop(self, ev):
        ev.preventDefault()
        self._on_drop_stop()

        def apply_text(s):
            self._input_element.value = s

        if ev.dataTransfer.items:
            for i in range(len(ev.dataTransfer.items)):
                if ev.dataTransfer.items[i].kind == "file":
                    file = ev.dataTransfer.items[i].getAsFile()
                    ext = file.name.lower().split(".")[-1]
                    if ext in ("xls", "xlsx", "xlsm", "pdf"):
                        self._analysis_out.innerHTML = (
                            f"Cannot process <u>{file.name}</u>. Drop a .csv file or "
                            + f"copy the columns in Excel and paste here."
                        )
                        continue
                    reader = window.FileReader()
                    reader.onload = lambda: apply_text(reader.result)
                    reader.readAsText(file)
                    self._analysis_out.innerHTML = f"Read from <u>{file.name}</u>"
                    break  # only process first one

    def _on_edit(self):
        # This length estimate is only correct if the tags are formatted
        # correctly, i.e. no whitespace or non-tag words. The actual
        # length can only really be obtained by collecting all tags
        # from the text and stringifying it with json, but that would
        # be too slow to do on each key press (there can be MANY lines).
        # We take the normal length, plus 2 per line for quotes, and 4 for braces.
        length_est = self._input_element.value.length
        length_est += self._input_element.value.count("\n") * 2 + 4
        if length_est >= stores.JSON_MAX:
            self._input_element.style.setProperty("outline", "dashed 2px red")
        else:
            self._input_element.style.setProperty("outline", "")

    def _load_current(self):
        item = window.store.settings.get_by_key("tag_presets")
        lines = (None if item is None else item.value) or []
        text = "\n".join(lines)
        if text:
            text += "\n"
        self._input_element.value = text

    def do_apply(self):
        """Normalize tags"""
        # Process
        self._analysis_out.innerHTML = "Processing ..."
        lines1 = self._input_element.value.lstrip().splitlines()
        lines2 = []
        found_tags = {}
        for line in lines1:
            line = line.strip()
            if line:
                tags, _ = utils.get_tags_and_parts_from_string(to_str(line), False)
                for tag in tags:
                    found_tags[tag] = tag
                line = tags.join(" ")
            lines2.append(line)

        # Check size
        length = JSON.stringify(lines2).length
        if length >= stores.JSON_MAX:
            self._input_element.style.setProperty("outline", "dashed 2px red")
            self._analysis_out.innerHTML = (
                f"Sorry, used {length} of max {stores.JSON_MAX-1} chars."
            )
            return

        # Save
        item = window.store.settings.create("tag_presets", lines2)
        window.store.settings.put(item)

        # Report
        self._load_current()
        ntags = len(found_tags.keys())
        self._analysis_out.innerHTML = (
            "<i class='fas'>\uf00c</i> Saved "
            + len(lines2)
            + " presets, with "
            + ntags
            + " unique tags."
        )


class TagRenameDialog(BaseDialog):
    """Dialog to rename tags."""

    def open(self, tags, callback=None):
        # Put in deterministic order
        if isinstance(tags, str):
            tags = tags.split(" ")
        tags.sort()
        self._tagz = tagz = tags.join(" ")

        self._tags1 = tags
        self._tags2 = []

        if len(tags) == 1:
            title = "Current tag name"
            tagword = "tag"
        else:
            title = "Tag combi to rename"
            tagword = "tags"

        self.maindiv.innerHTML = f"""
            <h1><i class='fas'>\uf02b</i>&nbsp;&nbsp;Rename {tagword}
                <button type='button'><i class='fas'>\uf00d</i></button>
                </h1>
            <div class='formlayout'>
                <div>{title}:</div>
                <div>{tagz}</div>
                <div>New tag(s):</div>
                <input type='text' spellcheck='false' />
                <div></div>
                <button type='button'>Prepare renaming ...</button>
                <div></div>
                <button type='button'>Confirm</button>
            </div>
            <div style='margin-top:2em;'></div>
        """

        close_but = self.maindiv.children[0].children[-1]
        close_but.onclick = self.close

        formdiv = self.maindiv.children[1]
        self._tagname2 = formdiv.children[3]
        self._button_replace = formdiv.children[5]
        self._button_replace_comfirm = formdiv.children[7]

        self._tagname2.oninput = self._hide_confirm_button
        self._tagname2.onchange = self._on_name2_done
        self._tagname2.onkeydown = self._on_key2

        self._button_replace.onclick = self._replace_all
        self._button_replace_comfirm.onclick = self._really_replace_all

        self._button_replace_comfirm.disabled = True
        self._button_replace_comfirm.style.visibility = "hidden"

        self._records = []

        super().open(callback)
        if utils.looks_like_desktop():
            self._tagname2.focus()

    def close(self):
        self._records = []
        super().close()

    def _hide_confirm_button(self):
        self._button_replace_comfirm.disabled = True
        self._button_replace_comfirm.style.visibility = "hidden"
        self._button_replace_comfirm.innerText = "Confirm"

    def _on_name2_done(self):
        raw_parts = self._tagname2.value.split(" ")
        text2 = ["#" + p for p in raw_parts].join(" ")
        tags2, _ = utils.get_tags_and_parts_from_string(text2)
        self._tags2 = tags2
        self._tagname2.value = " ".join(tags2)

    def _on_key2(self, e):
        key = e.key.lower()
        if key == "enter" or key == "return":
            e.stopPropagation()
            e.preventDefault()
            self._on_name2_done()
            self._replace_all()

    def _find_records(self):
        records = []

        # Early exit?
        if not self._tags1:
            self._records = []
            return
        # Get list of records
        for record in window.store.records.get_dump():
            tags = window.store.records.tags_from_record(record)  # also #untagged
            all_ok = True
            for tag in self._tags1:
                if tag not in tags:
                    all_ok = False
            if all_ok:
                records.push([record.t1, record.key])

        records.sort(key=lambda x: x[0])
        self._records = [x[1] for x in records]

    def _replace_all(self):
        self._find_records()
        tagword = "tag" if len(self._tags1) == 1 else "tags"

        n = len(self._records)
        if n == 0:
            text = f"No records found"
            disabled = True
        elif len(self._tags2):
            text = f"Confirm replacing {tagword} in {n} records"
            disabled = False
        else:
            text = f"Confirm removing {tagword} in {n} records"
            disabled = False

        self._button_replace_comfirm.innerText = text
        self._button_replace_comfirm.disabled = disabled
        self._button_replace_comfirm.style.visibility = "visible"

    def _really_replace_all(self):
        search_tags = self._tags1
        replacement_tags = self._tags2

        for key in self._records:
            record = window.store.records.get_by_key(key)
            _, parts = utils.get_tags_and_parts_from_string(record.ds)
            # Get updated parts
            new_parts = []
            replacement_made = False
            for part in parts:
                if part.startswith("#") and (
                    part in search_tags or part in replacement_tags
                ):
                    if not replacement_made:
                        replacement_made = True
                        new_parts.push(" ".join(replacement_tags))
                else:
                    new_parts.push(part)
            # Submit
            record.ds = "".join(new_parts)
            window.store.records.put(record)

        # Also update tag info
        if len(search_tags) == 1 and len(replacement_tags) == 1:
            tag1, tag2 = search_tags[0], replacement_tags[0]
            info = window.store.settings.get_tag_info(tag1)
            window.store.settings.set_tag_info(tag1, {})
            window.store.settings.set_tag_info(tag2, info)

        # Feedback
        self._button_replace_comfirm.innerText = "Done"
        self._button_replace_comfirm.disabled = True
        window.setTimeout(self._hide_confirm_button, 500)


class SearchDialog(BaseDialog):
    """Dialog to search for records and tags."""

    def open(self):
        self.maindiv.innerHTML = """
            <h1><i class='fas'>\uf002</i>&nbsp;&nbsp;Search records and tags
                <button type='button'><i class='fas'>\uf00d</i></button>
                </h1>
            <p>This tool allows you to search records by tags and plain text.
            Prepend tags/words with "!" to exclude records that match it.
            <br><br>
            </p>
            <div class='container' style='position: relative;'>
                <input type='text' style='width:100%;' spellcheck='false' />
                <div class='tag-suggestions-autocomp'></div>
            </div>
            <div style='font-size: smaller;'></div>
            <br>
            <button type='button'>Search</button>
            <button type='button'>Manage tags</button>
            <hr />
            <div class='record_grid' style='min-height:100px'></div>
        """

        close_but = self.maindiv.children[0].children[-1]
        close_but.onclick = self.close

        self._records_node = self.maindiv.children[-1]

        (
            _,  # h1
            _,  # p
            search_container,
            self._info_div,
            _,  # br
            self._search_but,
            self._tagmanage_but,
        ) = self.maindiv.children

        self._search_input, self._autocompleter_div = search_container.children
        self._search_input.placeholder = "Tags or text to search for ..."

        self._search_input.oninput = self._on_user_edit
        self._search_input.onchange = self._on_user_edit_done
        self._search_input.onkeydown = self._on_key

        self._search_but.onclick = self._find_records
        self._tagmanage_but.onclick = self._open_tag_dialog

        self._search_but.disabled = True
        self._tagmanage_but.disabled = True

        self._autocompleter = Autocompleter(
            self._autocompleter_div, self._search_input, self._autocomp_finished, 1
        )

        window._search_dialog_open_record = self._open_record
        self._records = []

        self._current_pos_tags = []
        self._current_neg_tags = []
        self._current_pos_words = []
        self._current_neg_words = []

        super().open(None)
        self._check_names()
        if utils.looks_like_desktop():
            self._search_input.focus()

    def close(self):
        self._autocompleter.close()
        self._records = []
        super().close()

    def _autocomp_finished(self):
        self._check_names()

    def _on_user_edit(self):
        self._autocompleter.init()
        self._check_names()

    def _on_user_edit_done(self):
        self._autocompleter.clear()

    def _check_names(self):
        text = self._search_input.value.lower()

        _, parts = utils.get_tags_and_parts_from_string(text)

        pos_tags = []
        neg_tags = []
        pos_words = []
        neg_words = []

        nex_tag_is_neg = False
        for part in parts:
            this_tag_is_neg = nex_tag_is_neg
            nex_tag_is_neg = False
            if part.startswith("#"):
                if this_tag_is_neg:
                    neg_tags.append(part.lower())
                else:
                    pos_tags.append(part.lower())
            else:
                for word in part.split(" "):
                    word = word.strip()
                    if not word:
                        pass
                    elif word == "!":
                        nex_tag_is_neg = True
                    elif word.startswith("!"):
                        neg_words.append(word[1:])
                    else:
                        pos_words.append(word)

        self._current_pos_tags = pos_tags
        self._current_neg_tags = neg_tags
        self._current_pos_words = pos_words
        self._current_neg_words = neg_words

        # Process search button
        if pos_tags or neg_tags or pos_words or neg_words:
            self._search_but.disabled = False
        else:
            self._search_but.disabled = True

        # Process tags button
        if len(pos_tags) > 0:
            if len(pos_tags) == 1:
                icon = "<i class='fas'>\uf02b</i>&nbsp;&nbsp;"
            else:
                icon = "<i class='fas'>\uf02c</i>&nbsp;&nbsp;"
            self._tagmanage_but.innerHTML = f"{icon} Manage {pos_tags.join(' ')}"
            self._tagmanage_but.disabled = False
        else:
            self._tagmanage_but.innerHTML = "Manage tags"
            self._tagmanage_but.disabled = True

        self._show_what_would_be_searched()

    def _on_key(self, e):
        key = e.key.lower()
        if self._autocompleter.on_key(e):
            e.stopPropagation()
            return
        elif key == "enter" or key == "return":
            e.stopPropagation()
            e.preventDefault()
            self._find_records()
        else:
            super()._on_key(e)

    def _find_records(self):
        records = []

        pos_tags = self._current_pos_tags
        neg_tags = self._current_neg_tags
        pos_words = self._current_pos_words
        neg_words = self._current_neg_words

        is_hidden = window.stores.is_hidden

        if (
            len(pos_tags) > 0
            or len(neg_tags) > 0
            or len(pos_words) > 0
            or len(neg_words) > 0
        ):
            # Get list of records
            for record in window.store.records.get_dump():
                if is_hidden(record):
                    continue
                # Check tags
                tags = window.store.records.tags_from_record(record)  # also #untagged
                all_tags_ok = True
                for tag in pos_tags:
                    if tag not in tags:
                        all_tags_ok = False
                        break
                for tag in neg_tags:
                    if tag in tags:
                        all_tags_ok = False
                        break
                if not all_tags_ok:
                    continue
                # Check strings
                ds = (record.ds or "").lower()
                all_strings_ok = True
                for word in pos_words:
                    if word not in ds:
                        all_strings_ok = False
                        break
                for word in neg_words:
                    if word in ds:
                        all_strings_ok = False
                        break
                if not all_strings_ok:
                    continue
                # All checks passed
                records.push([record.t1, record.key])

        records.sort(key=lambda x: -x[0])
        self._records = [x[1] for x in records]
        self._show_records()
        self._check_names()

    def _show_what_would_be_searched(self):
        any = False
        find_html = f"Search rules:<ul>"
        if len(self._current_pos_tags) > 0:
            any = True
            bold_tags = [f"<b>{tag}</b>" for tag in self._current_pos_tags]
            find_html += "<li>Including tag" + (
                "s" if len(self._current_pos_tags) > 1 else ""
            )
            find_html += " " + ", ".join(bold_tags) + "</li>"
        if len(self._current_neg_tags) > 0:
            any = True
            bold_tags = [f"<b>{tag}</b>" for tag in self._current_neg_tags]
            find_html += "<li>Excluding tag" + (
                "s" if len(self._current_neg_tags) > 1 else ""
            )
            find_html += " " + ", ".join(bold_tags) + "</li>"
        if len(self._current_pos_words) > 0:
            any = True
            italic_words = [f"<i>'{word}'</i>" for word in self._current_pos_words]
            find_html += " <li>Including word" + (
                "s" if len(self._current_pos_words) > 1 else ""
            )
            find_html += " " + ", ".join(italic_words) + "</li>"
        if len(self._current_neg_words) > 0:
            any = True
            italic_words = [f"<i>'{word}'</i>" for word in self._current_neg_words]
            find_html += " <li>Excluding word" + (
                "s" if len(self._current_neg_words) > 1 else ""
            )
            find_html += " " + ", ".join(italic_words) + "</li>"
        find_html += "</ul>"
        self._info_div.innerHTML = find_html if any else ""

    def _show_records(self):
        lines = [f"Found {self._records.length} records:<br>"]
        for key in self._records:
            record = window.store.records.get_by_key(key)
            ds = record.ds or ""
            date = dt.time2str(record.t1).split("T")[0]
            lines.append(
                f"""
                <a href='#date={date}'
                    style='cursor: pointer;'>
                    <span>{date}</span>
                </a>&nbsp;&nbsp;
                <a onclick='window._search_dialog_open_record("{key}")'
                    style='cursor: pointer;'>
                    <i class='fas'>\uf682</i>
                    <span>{ds}</span>
                </a>
                """
            )
        self._records_node.innerHTML = "<br />\n".join(lines)

    def _open_record(self, key):
        record = window.store.records.get_by_key(key)
        self._canvas.record_dialog.open("Edit", record, self._show_records)

    def _open_tag_dialog(self):
        if len(self._current_pos_tags) == 1:
            tagz = self._current_pos_tags[0]
            self._canvas.tag_dialog.open(tagz, self._show_records)
        elif len(self._current_pos_tags) > 1:
            tagz = " ".join(self._current_pos_tags)
            self._canvas.tag_combo_dialog.open(tagz, self._show_records)


class ReportDialog(BaseDialog):
    """A dialog that shows a report of records, and allows exporting."""

    def open(self, t1=None, t2=None, tags=None):
        """Show/open the dialog ."""

        if t1 is None or t2 is None:
            t1, t2 = self._canvas.range.get_target_range()
        if tags is None:
            tags = self._canvas.widgets.AnalyticsWidget.selected_tags

        self._tags = tags or []

        # Transform time int to dates.
        t1_date = dt.time2localstr(dt.round(t1, "1D")).split(" ")[0]
        t2_date = dt.time2localstr(dt.round(t2, "1D")).split(" ")[0]
        if t1_date != t2_date:
            # The date range is inclusive (and we add 1D later): move back one day
            t2_date = dt.time2localstr(dt.add(dt.round(t2, "1D"), "-1D")).split(" ")[0]
        self._t1_date = t1_date
        self._t2_date = t2_date

        # Generate preamble
        if self._tags:
            filtertext = self._tags.join(" ")
        else:
            filtertext = "<small>Select tags in overview panel</small>"
        self._copybuttext = "Copy table"
        html = f"""
            <h1><i class='fas'>\uf15c</i>&nbsp;&nbsp;Report
                <button type='button'><i class='fas'>\uf00d</i></button>
                </h1>
            <div class='formlayout'>
                <div>Tags:</div> <div>{filtertext}</div>
                <div>Date range:</div> <div style='font-size:smaller;'></div>
                <div>Grouping:</div> <select>
                                        <option value='none'>none</option>
                                        <option value='tagz'>tags</option>
                                        <option value='ds'>description</option>
                                     </select>
                <div>Group by period:</div> <select>
                                        <option value='none'>none</option>
                                        <option value='day'>day</option>
                                        <option value='week'>week</option>
                                        <option value='month'>month</option>
                                        <option value='quarter'>quarter</option>
                                        <option value='year'>year</option>
                                     </select>
                <div>Tag order:</div> <label><input type='checkbox' /> Hide secondary tags</label>
                <div>Duration format:</div> <select>
                                        <option value='h0'>9</option>
                                        <option value='hm'>9:07</option>
                                        <option value='hms'>9:07:24</option>
                                        <option value='h1'>9.1</option>
                                        <option value='h2'>9.12</option>
                                        <option value='h3'>9.123</option>
                                     </select>
                <div>Details:</div> <label><input type='checkbox' checked /> Show records</label>
                <button type='button'><i class='fas'>\uf328</i>&nbsp;&nbsp;{self._copybuttext}</button>
                    <div>paste in a spreadsheet</div>
                <button type='button'><i class='fas'>\uf0ce</i>&nbsp;&nbsp;Save CSV</button>
                    <div>save spreadsheet (more details)</div>
                <button type='button'><i class='fas'>\uf1c1</i>&nbsp;&nbsp;Save PDF</button>
                    <div>archive or send to a client</div>
            </div>
            <hr />
            <table id='report_table'></table>
        """

        self.maindiv.innerHTML = html
        self._table_element = self.maindiv.children[-1]
        form = self.maindiv.children[1]

        # filter text = form.children[1]
        self._date_range = form.children[3]
        self._grouping_select = form.children[5]
        self._groupperiod_select = form.children[7]
        self._hidesecondary_but = form.children[9].children[0]  # inside label
        self._format_but = form.children[11]
        self._showrecords_but = form.children[13].children[0]  # inside label
        self._copy_but = form.children[14]
        self._savecsv_but = form.children[16]
        self._savepdf_but = form.children[18]

        # Connect input elements
        close_but = self.maindiv.children[0].children[-1]
        close_but.onclick = self.close
        self._date_range.innerHTML = (
            dt.format_isodate(t1_date)
            + "&nbsp;&nbsp;&ndash;&nbsp;&nbsp;"
            + dt.format_isodate(t2_date)
        )
        self._date_range.innerHTML += (
            "&nbsp;&nbsp;<button type='button'><i class='fas'>\uf073</i></button>"
        )
        date_button = self._date_range.children[0]
        date_button.onclick = self._user_chose_date
        #
        grouping = window.simplesettings.get("report_grouping")
        self._grouping_select.value = grouping
        groupperiod = window.simplesettings.get("report_groupperiod")
        self._groupperiod_select.value = groupperiod
        hidesecondary = window.simplesettings.get("report_hidesecondary")
        self._hidesecondary_but.checked = hidesecondary
        format = window.simplesettings.get("report_format")
        self._format_but.value = format
        showrecords = window.simplesettings.get("report_showrecords")
        self._showrecords_but.checked = showrecords
        #
        self._grouping_select.onchange = self._on_setting_changed
        self._groupperiod_select.onchange = self._on_setting_changed
        self._hidesecondary_but.oninput = self._on_setting_changed
        self._format_but.onchange = self._on_setting_changed
        self._showrecords_but.oninput = self._on_setting_changed
        #
        self._copy_but.onclick = self._copy_clipboard
        self._savecsv_but.onclick = self._save_as_csv
        self._savepdf_but.onclick = self._save_as_pdf

        window.setTimeout(self._update_table)
        super().open(None)

    def _user_chose_date(self):
        self.close()
        self._canvas.timeselection_dialog.open(self.open)

    def _on_setting_changed(self):
        window.simplesettings.set("report_grouping", self._grouping_select.value)
        window.simplesettings.set("report_groupperiod", self._groupperiod_select.value)
        window.simplesettings.set(
            "report_hidesecondary", self._hidesecondary_but.checked
        )
        window.simplesettings.set("report_format", self._format_but.value)
        window.simplesettings.set("report_showrecords", self._showrecords_but.checked)
        self._update_table()

    def _update_table(self):
        t1_date = self._t1_date
        t2_date = self._t2_date
        if not float(t1_date.split("-")[0]) > 1899:
            self._table_element.innerHTML = ""
            return
        elif not float(t2_date.split("-")[0]) > 1899:
            self._table_element.innerHTML = ""
            return

        t1 = str_date_to_time_int(t1_date)
        t2 = str_date_to_time_int(t2_date)
        t2 = dt.add(t2, "1D")  # look until the end of the day

        self._last_t1, self._last_t2 = t1, t2
        html = self._generate_table_html(self._generate_table_rows(t1, t2))
        self._table_element.innerHTML = html

        # Configure the table ...
        if self._showrecords_but.checked:
            self._table_element.classList.add("darkheaders")
        else:
            self._table_element.classList.remove("darkheaders")

        # Also apply in the app itself!
        window.canvas.range.animate_range(t1, t2, None, False)  # without snap

    def _generate_table_rows(self, t1, t2):
        showrecords = self._showrecords_but.checked

        format = self._format_but.value
        if format == "h0":
            round_duration = lambda t: Math.round(t / 3600) * 3600
            duration2str = lambda t: f"{t/3600:0.0f}"
        elif format == "h1":
            round_duration = lambda t: Math.round(t / 360) * 360
            duration2str = lambda t: f"{t/3600:0.1f}"
        elif format == "h2":
            round_duration = lambda t: Math.round(t / 36) * 36
            duration2str = lambda t: f"{t/3600:0.2f}"
        elif format == "h3":
            round_duration = lambda t: Math.round(t / 3.6) * 3.6
            duration2str = lambda t: f"{t/3600:0.3f}"
        elif format == "h4":
            round_duration = lambda t: Math.round(t / 0.36) * 0.36
            duration2str = lambda t: f"{t/3600:0.4f}"
        elif format == "hms":
            round_duration = lambda t: Math.round(t)
            duration2str = lambda t: dt.duration_string_colon(t, True)
        else:  # fallback == "hm":
            round_duration = lambda t: Math.round(t / 60) * 60
            duration2str = lambda t: dt.duration_string_colon(t, False)

        # Get stats and sorted records, this already excludes hidden records
        stats = window.store.records.get_stats(t1, t2).copy()
        records = window.store.records.get_records(t1, t2).values()
        records.sort(key=lambda record: record.t1)

        # Set (appropriately rounded) durations
        for i in range(len(records)):
            record = records[i]
            record.duration = round_duration(min(t2, record.t2) - max(t1, record.t1))

        # Determine priorities
        priorities = {}
        for tagz in stats.keys():
            tags = tagz.split(" ")
            for tag in tags:
                info = window.store.settings.get_tag_info(tag)
                priorities[tag] = info.get("priority", 0) or 1

        # Get better names
        name_map = utils.get_better_tag_order_from_stats(
            stats, self._tags, True, priorities
        )

        # Hide secondary tags by removing them from the mapping.
        # Note that this means that different keys now map to the same value.
        if self._hidesecondary_but.checked:
            for tagz1, tagz2 in name_map.items():
                tags = tagz2.split(" ")
                tags = [tag for tag in tags if priorities[tag] <= 1]
                tagz2 = tags.join(" ")
                name_map[tagz1] = tagz2

        # Create list of pairs of stat-name, stat-key, and sort.
        # This is the reference order for tagz.
        statobjects = {}
        for tagz1, tagz2 in name_map.items():
            t = statobjects.get(tagz2, {}).get("t", 0) + stats[tagz1]
            statobjects[tagz2] = {"tagz": tagz2, "t": t}
        statobjects = statobjects.values()
        utils.order_stats_by_duration_and_name(statobjects)

        # Get how to group the records
        group_method = self._grouping_select.value
        group_period = self._groupperiod_select.value
        empty_title = "General"

        # Perform primary grouping ...
        if group_method == "tagz":
            groups = {}
            for obj in statobjects:
                groups[obj.tagz] = {
                    "title": obj.tagz or empty_title,
                    "duration": 0,
                    "records": [],
                }
            for i in range(len(records)):
                record = records[i]
                tagz1 = window.store.records.tags_from_record(record).join(" ")
                if tagz1 not in name_map:
                    continue
                tagz2 = name_map[tagz1]
                group = groups[tagz2]
                group.records.push(record)
                group.duration += record.duration
            group_list1 = groups.values()

        elif group_method == "ds":
            groups = {}
            for i in range(len(records)):
                record = records[i]
                tagz1 = window.store.records.tags_from_record(record).join(" ")
                if tagz1 not in name_map:
                    continue
                ds = record.ds
                if ds not in groups:
                    groups[ds] = {"title": ds, "duration": 0, "records": []}
                group = groups[ds]
                group.records.push(record)
                group.duration += record.duration
            group_list1 = groups.values()
            group_list1.sort(key=lambda x: x.title.lower())

        else:
            group = {"title": "hidden", "duration": 0, "records": []}
            group_list1 = [group]
            for i in range(len(records)):
                record = records[i]
                tagz1 = window.store.records.tags_from_record(record).join(" ")
                if tagz1 not in name_map:
                    continue
                group.records.push(record)

        # Perform grouping for time ...
        if group_period == "none":
            group_list2 = group_list1
        else:
            groups = {}
            for group_index in range(len(group_list1)):
                group_title = group_list1[group_index].title
                for record in group_list1[group_index].records:
                    # Get period string
                    date = dt.time2localstr(record.t1).split(" ")[0]
                    year = int(date.split("-")[0])
                    if group_period == "day":
                        period = dt.format_isodate(date)
                    elif group_period == "week":
                        week = dt.get_weeknumber(record.t1)
                        period = f"{year}W{week}"
                    elif group_period == "month":
                        month = int(date.split("-")[1])
                        period = dt.MONTHS_SHORT[month - 1] + f" {year}"
                    elif group_period == "quarter":
                        month = int(date.split("-")[1])
                        q = "111222333444"[month - 1]
                        period = f"{year}Q{q}"
                    elif group_period == "year":
                        period = f"{year}"
                    else:
                        period = date  # fallback
                    # New title
                    # Note: can turn around title and sortkey to make the period the secondary group
                    if group_title == "hidden":
                        title = period
                        sortkey = date
                    else:
                        title = period + " / " + group_title
                        sortkey = date + str(1000000 + group_index)
                    if title not in groups:
                        groups[title] = {
                            "title": title,
                            "duration": 0,
                            "records": [],
                            "sortkey": sortkey,
                        }
                    # Append
                    group = groups[title]
                    group.records.push(record)
                    group.duration += record.duration

            # Get new groups, sorted by period
            group_list2 = groups.values()
            group_list2.sort(key=lambda x: x.sortkey)

        # Generate rows
        rows = []

        # Include total
        total_duration = 0
        for group in group_list2:
            total_duration += group.duration
        rows.append(["head", duration2str(total_duration), "Total", 0])

        for group in group_list2:
            # Add row for total of this tag combi
            duration = duration2str(group.duration)
            pad = 1
            if showrecords:
                rows.append(["blank"])
            if group.title != "hidden":
                rows.append(["head", duration, group.title, pad])

            # Add row for each record
            if showrecords:
                records = group.records
                for i in range(len(records)):
                    record = records[i]
                    sd1, st1 = dt.time2localstr(record.t1).split(" ")
                    sd2, st2 = dt.time2localstr(record.t2).split(" ")
                    if True:  # st1.endsWith(":00"):
                        st1 = st1[:-3]
                    if True:  # st2.endsWith(":00"):
                        st2 = st2[:-3]
                    duration = duration2str(record.duration)
                    rows.append(
                        [
                            "record",
                            record.key,
                            duration,
                            dt.format_isodate(sd1),
                            st1,
                            st2,
                            to_str(record.get("ds", "")),  # strip tabs and newlines
                            window.store.records.tags_from_record(record).join(" "),
                        ]
                    )

        return rows

    def _generate_table_html(self, rows):
        window._open_record_dialog = self._open_record
        blank_row = "<tr class='blank_row'><td></td><td></td><td></td><td></td><td></td><td></td><td></td></tr>"
        lines = []
        for row in rows:
            if row[0] == "blank":
                lines.append(blank_row)
            elif row[0] == "head":
                lines.append(
                    f"<tr><th>{row[1]}</th><th class='pad{row[3]}'>{row[2]}</th><th></th>"
                    + "<th></th><th></th><th></th><th></th></tr>"
                )
            elif row[0] == "record":
                _, key, duration, sd1, st1, st2, ds, tagz = row
                lines.append(
                    f"<tr><td></td><td></td><td>{duration}</td>"
                    + f"<td>{sd1}</td><td class='t1'>{st1}</td><td class='t2'>{st2}</td>"
                    + f"<td><a onclick='window._open_record_dialog(\"{key}\")' style='cursor:pointer;'>"
                    + f"{ds or '&nbsp;-&nbsp;'}</a></td></tr>"
                )
        return lines.join("")

    def _open_record(self, key):
        record = window.store.records.get_by_key(key)
        self._canvas.record_dialog.open("Edit", record, self._update_table)

    def _copy_clipboard(self):
        tools.copy_dom_node(self._table_element)
        self._copy_but.innerHTML = (
            f"<i class='fas'>\uf46c</i>&nbsp;&nbsp;{self._copybuttext}"
        )
        window.setTimeout(self._reset_copy_but_text, 800)

    def _reset_copy_but_text(self):
        self._copy_but.innerHTML = (
            f"<i class='fas'>\uf328</i>&nbsp;&nbsp;{self._copybuttext}"
        )

    def _get_export_filename(self, ext):
        date1 = self._t1_date.replace("-", "")
        date2 = self._t2_date.replace("-", "")
        if date1 == date2:
            return f"timetagger-{date1}.{ext}"
        else:
            return f"timetagger-{date1}-{date2}.{ext}"

    def _save_as_csv(self):
        # This is all pretty straightforward. The most tricky bit it
        # the ds (description). It can have any Unicode, so it should
        # surrounded by double quotes. Any double-quotes inside the ds
        # must be escaped by doubling them. And finally, don't put space
        # after comma's, or tools like Excel may not be able to parse
        # the quoted string correctly. Note that in _generate_table_rows
        # the ds is stipped from \t\r\n.

        rows = self._generate_table_rows(self._last_t1, self._last_t2)

        lines = []
        lines.append(
            "subtotals,tag_groups,duration,date,start,stop,description,user,tags"
        )
        lines.append("")

        user = ""  # noqa
        if window.store.get_auth:
            auth = window.store.get_auth()
            if auth:
                user = auth.username  # noqa

        for row in rows:
            if row[0] == "blank":
                lines.append(",,,,,,,,")
            elif row[0] == "head":
                lines.append(RawJS('row[1] + "," + row[2] + ",,,,,,,"'))
            elif row[0] == "record":
                _, key, duration, sd1, st1, st2, ds, tagz = row
                ds = '"' + ds.replace('"', '""') + '"'
                lines.append(
                    RawJS(
                        """',,' + duration + ',' + sd1 + ',' + st1 + ',' + st2 + ',' + ds + ',' + user + ',' + tagz"""
                    )
                )

        # Get blob wrapped in an object url
        obj_url = window.URL.createObjectURL(
            window.Blob(["\r\n".join(lines)], {"type": "text/csv"})
        )
        # Create a element to attach the download to
        a = document.createElement("a")
        a.style.display = "none"
        a.setAttribute("download", self._get_export_filename("csv"))
        a.href = obj_url
        document.body.appendChild(a)
        # Trigger the download by simulating click
        a.click()
        # Cleanup
        window.URL.revokeObjectURL(a.href)
        document.body.removeChild(a)

    def _save_as_pdf(self):
        # Configure
        width, height = 210, 297  # A4
        margin = 20  # mm
        showrecords = self._showrecords_but.checked
        rowheight = 6
        rowheight2 = rowheight / 2
        rowskip = 3
        coloffsets = 15, 4, 17, 10, 10

        # Get row data and divide in chunks. This is done so that we
        # can break pages earlier to avoid breaking chunks.
        rows = self._generate_table_rows(self._last_t1, self._last_t2)
        chunks = [[]]
        for row in rows:
            if row[0] == "blank":
                chunks.append([])
            else:
                chunks[-1].append(row)

        # Initialize the document
        doc = window.jsPDF()
        doc.setFont("Ubuntu-C")

        # Draw preamble
        doc.setFontSize(24)
        doc.text("Time record report", margin, margin, {"baseline": "top"})
        img = document.getElementById("ttlogo_bd")
        doc.addImage(img, "PNG", width - margin - 30, margin, 30, 30)
        # doc.setFontSize(12)
        # doc.text(
        #     "TimeTagger",
        #     width - margin,
        #     margin + 22,
        #     {"align": "right", "baseline": "top"},
        # )

        tagname = self._tags.join(" ") if self._tags else "all"
        d1 = dt.format_isodate(self._t1_date)
        d2 = dt.format_isodate(self._t2_date)
        doc.setFontSize(11)
        doc.text("Tags:  ", margin + 20, margin + 15, {"align": "right"})
        doc.text(tagname, margin + 20, margin + 15)
        doc.text("From:  ", margin + 20, margin + 20, {"align": "right"})
        doc.text(d1, margin + 20, margin + 20)
        doc.text("Until:  ", margin + 20, margin + 25, {"align": "right"})
        doc.text(d2, margin + 20, margin + 25)

        # Prepare drawing table
        doc.setFontSize(10)
        left_middle = {"align": "left", "baseline": "middle"}
        right_middle = {"align": "right", "baseline": "middle"}
        y = margin + 35

        # Draw table
        npages = 1
        for chunknr in range(len(chunks)):
            # Maybe insert a page break early to preserve whole chunks
            space_used = y - margin
            space_total = height - 2 * margin
            if space_used > 0.9 * space_total:
                rowsleft = sum([len(chunk) for chunk in chunks[chunknr:]])
                space_needed = rowsleft * rowheight
                space_needed += (len(chunks) - chunknr) * rowskip
                if space_needed > space_total - space_used:
                    doc.addPage()
                    npages += 1
                    y = margin

            for rownr, row in enumerate(chunks[chunknr]):
                # Add page break?
                if (y + rowheight) > (height - margin):
                    doc.addPage()
                    npages += 1
                    y = margin

                if row[0] == "head":
                    if showrecords:
                        doc.setFillColor("#ccc")
                    else:
                        doc.setFillColor("#f3f3f3" if rownr % 2 else "#eaeaea")
                    doc.rect(margin, y, width - 2 * margin, rowheight, "F")
                    # Duration
                    doc.setTextColor("#000")
                    x = margin + coloffsets[0]
                    doc.text(row[1], x, y + rowheight2, right_middle)  # duration
                    # Tag names, add structure via color, no padding
                    basename, lastname = "", row[2]
                    doc.setTextColor("#555")
                    x += coloffsets[1]
                    doc.text(basename, x, y + rowheight2, left_middle)
                    doc.setTextColor("#000")
                    x += doc.getTextWidth(basename)
                    doc.text(lastname, x, y + rowheight2, left_middle)

                elif row[0] == "record":
                    doc.setFillColor("#f3f3f3" if rownr % 2 else "#eaeaea")
                    doc.rect(margin, y, width - 2 * margin, rowheight, "F")
                    doc.setTextColor("#000")
                    # _, key, duration, sd1, st1, st2, ds, tagz = row
                    # The duration is right-aligned
                    x = margin + coloffsets[0]
                    doc.text(row[2], x, y + rowheight2, right_middle)
                    # The rest (sd1, st1, st2) is left-aligned
                    for i in (1, 2, 3):
                        x += coloffsets[i]
                        s = row[i + 2]
                        if i == 3:  # st2
                            doc.text("-", x - 1, y + rowheight2, right_middle)
                        doc.text(s, x, y + rowheight2, left_middle)
                    # The description may be so long we need to split it
                    x += coloffsets[4]
                    min_x = x
                    max_x = width - margin
                    ds = row[6]
                    if x + doc.getTextWidth(ds) <= max_x:
                        doc.text(ds, x, y + rowheight2, left_middle)
                    else:
                        w_space = doc.getTextWidth(" ")
                        for word in ds.split(" "):
                            w = doc.getTextWidth(word)
                            if x + w > max_x:  # need new line
                                x = min_x
                                y += rowheight
                                doc.setFillColor("#f3f3f3" if rownr % 2 else "#eaeaea")
                                doc.rect(margin, y, width - 2 * margin, rowheight, "F")
                                doc.setTextColor("#000")
                            doc.text(word, x, y + rowheight2, left_middle)
                            x += w + w_space
                else:
                    doc.setFillColor("#ffeeee")
                    doc.rect(margin, y, width - 2 * margin, rowheight, "F")

                y += rowheight
            y += rowskip

        # Add pagination
        doc.setFontSize(8)
        doc.setTextColor("#555")
        for i in range(npages):
            pagenr = i + 1
            doc.setPage(pagenr)
            x, y = width - 0.5 * margin, 0.5 * margin
            doc.text(f"{pagenr}/{npages}", x, y, {"align": "right", "baseline": "top"})

        doc.save(self._get_export_filename("pdf"))
        # doc.output('dataurlnewwindow')  # handy during dev


class ExportDialog(BaseDialog):
    """Dialog to export data."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self._dtformat = "local"
        self._working = 0

    def open(self, callback=None):
        self.maindiv.innerHTML = f"""
            <h1><i class='fas'>\uf56e</i>&nbsp;&nbsp;Export
                <button type='button'><i class='fas'>\uf00d</i></button>
            </h1>
            <p>
            The table below contains all your records. This can be
            useful for backups, processing, or to move your data
            elsewhere.
            </p><p>&nbsp;</p>
            <div>
                <span>Date-time format:</span>
                &nbsp;<input type="radio" name="dtformat" value="local" checked> Local</input>
                &nbsp;<input type="radio" name="dtformat" value="unix"> Unix</input>
                &nbsp;<input type="radio" name="dtformat" value="iso"> ISO 8601</input>
            </div>
            <button type='button'>Copy</button>
            <hr />
            <table id='export_table'></table>
            """

        self._table_element = self.maindiv.children[-1]
        self._table_element.classList.add("darkheaders")

        self._copy_but = self.maindiv.children[-3]
        self._copy_but.onclick = self._copy_clipboard
        self._copy_but.disabled = True

        radio_buttons = self.maindiv.children[-4].children
        for i in range(1, len(radio_buttons)):
            but = radio_buttons[i]
            but.onchange = self._on_dtformat

        self._cancel_but = self.maindiv.children[0].children[-1]
        self._cancel_but.onclick = self.close
        super().open(callback)

        self.fill_records()

    def _on_dtformat(self, e):
        self._dtformat = e.target.value
        self.fill_records()

    async def fill_records(self):
        self._working += 1
        working = self._working
        await window.tools.sleepms(100)

        # Prepare
        self._copy_but.disabled = True
        itemsdict = window.store.records._items
        lines = []

        # Add header
        lineparts = ["key", "start", "stop", "tags", "description"]
        lines.append("<tr><th>" + lineparts.join("</th><th>") + "</th></tr>")

        # Parse all items
        # Take care that description does not have newlines or tabs, using to_str
        # With tab-separated values it is not common to surround values in quotes.
        for key in itemsdict.keys():
            item = itemsdict[key]
            if not window.stores.is_hidden(item):
                t1, t2 = item.t1, item.t2
                if self._dtformat == "local":
                    t1, t2 = dt.time2localstr(t1), dt.time2localstr(t2)
                elif self._dtformat == "iso":
                    t1, t2 = dt.time2str(t1, 0), dt.time2str(t2, 0)
                lineparts = [
                    item.key,
                    t1,
                    t2,
                    utils.get_tags_and_parts_from_string(item.ds)[0].join(" "),
                    to_str(item.get("ds", "")),
                ]
                lines.append("<tr><td>" + lineparts.join("</td><td>") + "</td></tr>")
            # Give feedback while processing
            if len(lines) % 256 == 0:
                self._copy_but.innerHTML = "Found " + len(lines) + " records"
                # self._table_element.innerHTML = lines.join("\n")
                await window.tools.sleepms(1)
            if working != self._working:
                return

        # Done
        self._copy_but.innerHTML = "Copy export-table <i class='fas'>\uf0ea</i>"
        self._table_element.innerHTML = lines.join("\n")
        self._copy_but.disabled = False

    def _copy_clipboard(self):
        table = self.maindiv.children[-1]
        tools.copy_dom_node(table)
        self._copy_but.innerHTML = "Copy export-table <i class='fas'>\uf46c</i>"
        window.setTimeout(self._reset_copy_but_text, 800)

    def _reset_copy_but_text(self):
        self._copy_but.innerHTML = "Copy export-table <i class='fas'>\uf0ea</i>"


class ImportDialog(BaseDialog):
    """Dialog to import data."""

    def __init__(self, canvas):
        super().__init__(canvas)

    def open(self, callback=None):
        self.maindiv.innerHTML = f"""
            <h1><i class='fas'>\uf56f</i>&nbsp;&nbsp;Import
                <button type='button'><i class='fas'>\uf00d</i></button>
            </h1>
            <p>
            Copy your table data (from e.g. a CSV file, a text file, or
            directly from Excel) and paste it in the text field below.
            CSV files can be dragged into the text field.
            See <a href='https://timetagger.app/articles/importing/'>this article</a>
            for details.
            </p><p>&nbsp;</p>
            <button type='button'>Analyse</button>
            <button type='button'>Import</button>
            <hr />
            <div></div>
            <textarea rows='12'
                style='background: #fff; display: block; margin: 0.5em; width: calc(100% - 1.5em);'>
            </textarea>
            """

        self._input_element = self.maindiv.children[-1]
        self._input_element.value = ""
        self._input_element.ondragexit = self._on_drop_stop
        self._input_element.ondragover = self._on_drop_over
        self._input_element.ondrop = self._on_drop

        if not (
            window.store.__name__.startswith("Demo")
            or window.store.__name__.startswith("Sandbox")
        ):
            maintext = self.maindiv.children[2]
            maintext.innerHTML += """
                Consider importing into the
                <a target='new' href='sandbox'>Sandbox</a> first.
                """

        self._analysis_out = self.maindiv.children[-2]

        self._analyse_but = self.maindiv.children[3]
        self._analyse_but.onclick = self.do_analyse
        self._import_but = self.maindiv.children[4]
        self._import_but.onclick = self.do_import
        self._import_but.disabled = True

        self._cancel_but = self.maindiv.children[0].children[-1]
        self._cancel_but.onclick = self.close
        super().open(callback)

    def _on_drop_stop(self, ev):
        self._input_element.style.background = None

    def _on_drop_over(self, ev):
        ev.preventDefault()
        self._input_element.style.background = "#DFD"

    def _on_drop(self, ev):
        ev.preventDefault()
        self._on_drop_stop()

        def apply_text(s):
            self._input_element.value = s

        if ev.dataTransfer.items:
            for i in range(len(ev.dataTransfer.items)):
                if ev.dataTransfer.items[i].kind == "file":
                    file = ev.dataTransfer.items[i].getAsFile()
                    ext = file.name.lower().split(".")[-1]
                    if ext in ("xls", "xlsx", "xlsm", "pdf"):
                        self._analysis_out.innerHTML = (
                            f"Cannot process <u>{file.name}</u>. Drop a .csv file or "
                            + f"copy the columns in Excel and paste here."
                        )
                        continue
                    reader = window.FileReader()
                    reader.onload = lambda: apply_text(reader.result)
                    reader.readAsText(file)
                    self._analysis_out.innerHTML = f"Read from <u>{file.name}</u>"
                    break  # only process first one

    async def do_analyse(self):
        """Analyze incoming data ..."""
        if self._analyzing:
            return

        # Prepare
        self._analyzing = True
        self._import_but.disabled = True
        self._import_but.innerHTML = "Import"
        self._records2import = []
        # Run
        try:
            await self._do_analyse()
        except Exception as err:
            console.warn(str(err))
        # Restore
        self._analyzing = False
        self._import_but.innerHTML = "Import"
        if len(self._records2import) > 0:
            self._import_but.disabled = False

    async def _do_analyse(self):
        global JSON

        def log(s):
            self._analysis_out.innerHTML += s + "<br />"

        # Init
        self._analysis_out.innerHTML = ""
        text = self._input_element.value.lstrip()
        header, text = text.lstrip().split("\n", 1)
        header = header.strip()
        text = text or ""

        # Parse header to get sepator
        sep, sepname, sepcount = "", "", 0
        for x, name in [("\t", "tab"), (",", "comma"), (";", "semicolon")]:
            if header.count(x) > sepcount:
                sep, sepname, sepcount = x, name, header.count(x)
        if not header:
            log("No data")
            return
        elif not sepcount or not sep:
            log("Could not determine separator (tried tab, comma, semicolon)")
            return
        else:
            log("Looks like the separator is " + sepname)

        # Get mapping to parse header names
        M = {
            "key": ["id", "identifier"],
            "projectkey": ["project key", "project id"],
            "projectname": ["project", "pr", "proj", "project name"],
            "tags": ["tags", "tag"],
            "t1": ["start", "begin", "start time", "begin time"],
            "t2": ["stop", "end", "stop time", "end time"],
            "description": ["summary", "comment", "title", "ds"],
            "projectpath": ["project path"],
            "date": [],
            "duration": [
                "duration h:m",
                "duration h:m:s",
                "duration hh:mm",
                "duration hh:mm:ss",
            ],
        }
        namemap = {}
        for key, options in M.items():
            namemap[key] = key
            for x in options:
                namemap[x] = key

        # Parse header to get names
        headerparts1 = csvsplit(header, sep)[0]
        headerparts2 = []
        headerparts_unknown = []
        for name in headerparts1:
            name = name.lower().replace("-", " ").replace("_", " ")
            if name in namemap:
                headerparts2.append(namemap[name])
            elif not name:
                headerparts2.append(None)
            else:
                headerparts_unknown.append(name)
                headerparts2.append(None)
        while headerparts2 and headerparts2[-1] is None:
            headerparts2.pop(-1)
        if headerparts_unknown:
            log("Ignoring some headers: " + headerparts_unknown.join(", "))
        else:
            log("All headers names recognized")

        # All required names headers present?
        if "t1" not in headerparts2:
            log("Missing required header for start time.")
            return
        elif "t2" not in headerparts2 and "duration" not in headerparts2:
            log("Missing required header for stop time or duration.")
            return

        # Get dict to map (t1, t2) to record key
        timemap = {}  # t1_t2 -> key
        for key, record in window.store.records._items.items():
            timemap[record.t1 + "_" + record.t2] = key

        # Now parse!
        year_past_epoch = 31536000  # So we can test that a timestamp is not a hh.mm
        records = []
        new_record_count = 0
        index = 0
        row = 0
        while index < len(text):
            row += 1
            try:
                # Get parts on this row
                lineparts, index = csvsplit(text, sep, index)
                if len("".join(lineparts).trim()) == 0:
                    continue  # skip empty rows
                # Build raw object
                raw = {}
                for j in range(min(len(lineparts), len(headerparts2))):
                    key = headerparts2[j]
                    if key is not None:
                        raw[key] = lineparts[j].strip()
                raw.more = lineparts[len(headerparts2) :]
                # Build record
                record = window.store.records.create(0, 0)
                record_key = None
                if raw.key:
                    record_key = raw.key  # dont store at record yet
                if raw.date:
                    # Prep date. Support both dd-mm-yyyy and yyy-mm-dd
                    date = raw.date.replace(".", "-")  # Some tools use dots
                    if len(date) == 10 and date.count("-") == 2:
                        if len(date.split("-")[-1]) == 4:
                            date = "-".join(reversed(date.split("-")))
                        raw.date_ok = date
                if True:  # raw.t1 always exists
                    record.t1 = float(raw.t1)
                    if not (isFinite(record.t1) and record.t1 > year_past_epoch):
                        record.t1 = Date(raw.t1).getTime() / 1000
                    if not isFinite(record.t1) and raw.date_ok:
                        # Try use date, Yast uses dots, reverse if needed
                        tme = raw.t1.replace(".", ":")
                        if 4 <= len(tme) <= 8 and 1 <= tme.count(":") <= 2:
                            # Note: on IOS, Date needs to be "yyyy-mm-ddThh:mm:ss"
                            # but people are unlikely to import on an ios device ... I hope.
                            record.t1 = Date(raw.date_ok + " " + tme).getTime() / 1000
                    record.t1 = Math.floor(record.t1)
                if True:  # raw.t2 or duration exists -
                    record.t2 = float(raw.t2)
                    if not (isFinite(record.t2) and record.t2 > year_past_epoch):
                        record.t2 = Date(raw.t2).getTime() / 1000
                    if not isFinite(record.t2) and raw.duration:
                        # Try use duration
                        duration = float(raw.duration)
                        if ":" in raw.duration:
                            duration_parts = raw.duration.split(":")
                            if len(duration_parts) == 2:
                                duration = float(duration_parts[0]) * 3600
                                duration += float(duration_parts[1]) * 60
                            elif len(duration_parts) == 3:
                                duration = float(duration_parts[0]) * 3600
                                duration += float(duration_parts[1]) * 60
                                duration += float(duration_parts[2])
                        record.t2 = record.t1 + float(duration)
                    if not isFinite(record.t2) and raw.date_ok:
                        # Try use date
                        tme = raw.t2.replace(".", ":")
                        if 4 <= len(tme) <= 8 and 1 <= tme.count(":") <= 2:
                            record.t2 = Date(raw.date_ok + " " + tme).getTime() / 1000
                    record.t2 = Math.ceil(record.t2)
                if raw.tags:  # If tags are given, use that
                    raw_tags = raw.tags.replace(",", " ").split()
                    tags = []
                    for tag in raw_tags:
                        tag = utils.convert_text_to_valid_tag(tag.trim())
                        if len(tag) > 2:
                            tags.push(tag)
                else:  # If no tags are given, try to derive tags from project name
                    project_name = raw.projectname or raw.projectkey or ""
                    if raw.projectpath:
                        project_parts = [raw.projectpath]
                        if raw.more and headerparts2[-1] == "projectpath":  # Yast
                            project_parts = [raw.projectpath.replace("/", " | ")]
                            for j in range(len(raw.more)):
                                if len(raw.more[j]) > 0:
                                    project_parts.append(
                                        raw.more[j].replace("/", " | ")
                                    )
                        project_parts.append(raw.projectname.replace("/", " | "))
                        project_name = "/".join(project_parts)
                    project_name = to_str(project_name)  # normalize
                    tags = []
                    if project_name:
                        tags = [utils.convert_text_to_valid_tag(project_name)]
                if True:
                    tags_dict = {}
                    for tag in tags:
                        tags_dict[tag] = tag
                    if raw.description:
                        tags, parts = utils.get_tags_and_parts_from_string(
                            raw.description
                        )
                        for tag in tags:
                            tags_dict.pop(tag, None)
                        tagz = " ".join(tags_dict.values())
                        record.ds = to_str(tagz + " " + raw.description)
                    else:
                        tagz = " ".join(tags_dict.values())
                        record.ds = tagz
                # Validate record
                if record.t1 == 0 or record.t2 == 0:
                    log(f"Item on row {row} has invalid start/stop times")
                    return
                if len(window.store.records._validate_items([record])) == 0:
                    log(
                        f"Item on row {row} does not pass validation: "
                        + JSON.stringify(record)
                    )
                    return
                record.t2 = max(record.t2, record.t1 + 1)  # no running records
                # Assign the right key based on given key or t1_t2
                if record_key is not None:
                    record.key = record_key
                else:
                    existing_key = timemap.get(record.t1 + "_" + record.t2, None)
                    if existing_key is not None:
                        record.key = existing_key
                # Add
                records.append(record)
                if window.store.records.get_by_key(record.key) is None:
                    new_record_count += 1
                # Keep giving feedback / dont freeze
                if row % 100 == 0:
                    self._import_but.innerHTML = f"Found {len(records)} records"
                    await window.tools.sleepms(1)
            except Exception as err:
                log(f"Error at row {row}: {err}")
                return

        # Store and give summary
        self._records2import = records
        log(f"Found {len(records)} ({new_record_count} new)")

    def do_import(self):
        """Do the import!"""
        window.store.records.put(*self._records2import)
        self._records2import = []
        self._import_but.disabled = True
        self._import_but.innerHTML = "Import done"


class SettingsDialog(BaseDialog):
    """Dialog to change user settings."""

    def __init__(self, canvas):
        super().__init__(canvas)

    def open(self, callback=None):
        # Get shortcuts html
        shortcuts = {
            "_dialogs": "<b>In dialogs</b>",
            "Enter": "Submit dialog",
            "Escape": "Close dialog",
            "_nav": "<b>Navigation</b>",
            "N/Home/End": "Snap to now",
            "D": "Select today",
            "W": "Select this week",
            "M": "Select this month",
            "Q": "Select this quarter",
            "Y": "Select this year",
            "↑/PageUp": "Step back in time",
            "↓/PageDown": "Step forward in time",
            "→": "Zoom in",
            "←": "Zoom out",
            "_other": "<b>Other</b>",
            "S": "Start the timer or add an earlier record",
            "Shift+S": "Resume the current/previous record",
            "X": "Stop the timer",
            "F": "Open search dialog",
            "T": "Select time range",
            "R": "Open report dialog",
            "I": "Open the guide",
            "Backspace": "Unselect all tags",
        }
        shortcuts_html = ""
        for key, expl in shortcuts.items():
            if key.startswith("_"):
                key = ""
            shortcuts_html += f"<div class='monospace'>{key}</div><div>{expl}</div>"

        html = f"""
            <h1><i class='fas'>\uf013</i>&nbsp;&nbsp;Settings
                <button type='button'><i class='fas'>\uf00d</i></button>
            </h1>

            <center style='font-size:80%'>User settings</center>
            <h2><i class='fas'>\uf4fd</i>&nbsp;&nbsp;Time representation</h2>
            <div class='formlayout'>
                <div>Week starts on:</div>
                <select>
                    <option value='0'>Sunday</option>
                    <option value='1'>Monday</option>
                    <option value='6'>Saturday</option>
                </select>
                <div>Workdays:</div>
                <select>
                    <option value='2'>Monday - Friday</option>
                    <option value='1'>Monday - Saturday</option>
                    <option value='0'>Monday - Sunday</option>
                </select>
                <div>Show dates as:</div>
                <select>
                    <option value='yyyy-mm-dd'>yyyy-mm-dd (ISO 8601)</option>
                    <option value='dd-mm-yyyy'>dd-mm-yyyy (default)</option>
                    <option value='mm/dd/yyyy'>mm/dd/yyyy (US)</option>
                </select>
                <div>Show time as:</div>
                <select>
                    <option value='auto'>Auto</option>
                    <option value='24h'>23:20</option>
                    <option value='ampm'>11:20 pm</option>
                </select>
                <div>Show duration as:</div>
                <select>
                    <option value='dhms'>1d3h20m</option>
                    <option value='hms'>27h20m</option>
                    <option value='colon'>27:20</option>
                </select>
                <div>Today starts at:</div>
                <select>
                    <option value='-3h'>21:00</option>
                    <option value='-2h'>22:00</option>
                    <option value='-1h'>23:00</option>
                    <option value=''>00:00</option>
                    <option value='1h'>01:00</option>
                    <option value='2h'>02:00</option>
                    <option value='3h'>03:00</option>
                    <option value='4h'>04:00</option>
                    <option value='5h'>05:00</option>
                    <option value='6h'>06:00</option>
                    <option value='7h'>07:00</option>
                    <option value='8h'>08:00</option>
                    <option value='9h'>09:00</option>
                </select>
                <div>Today duration:</div>
                <select>
                    <option value='-12h'>12h</option>
                    <option value=''>24h</option>
                </select>
            </div>
            <h2><i class='fas'>\uf085</i>&nbsp;&nbsp;Misc</h2>
            <div class='formlayout'>
                <div>Default tag color:</div>
                <select>
                    <option value='default'>Yellow</option>
                    <option value='tag_name'>From Name</option>
                    <option value='random'>Random</option>
                </select>
            </div>
            <label>
                <input type='checkbox' checked='true'></input>
                Show elapsed time below start-button
            </label>

            <hr style='margin-top: 1em;' />

            <center style='font-size:80%'>Settings for this device</center>
            <h2><i class='fas'>\uf3fa</i>&nbsp;&nbsp;Appearance</h2>
            <div class='formlayout'>
                <div>Light / dark:</div>
                <select>
                    <option value=0>Auto detect</option>
                    <option value=1>Light mode</option>
                    <option value=2>Dark mode</option>
                </select>
                <div>Width:</div>
                <select>
                    <option value='auto'>Auto scale</option>
                    <option value='1000'>Max 1000px</option>
                    <option value='1500'>Max 1500px</option>
                    <option value='full'>Full width</option>
                </select>
            </div>
            <h2><i class='fas'>\uf0e0</i>&nbsp;&nbsp;Notification</h2>
            <label>
                <input type='checkbox' checked='false'></input>
                Show notification when starting a record.</label>
            <h2><i class='fas'>\uf2f2</i>&nbsp;&nbsp;Pomodoro</h2>
            <label>
                <input type='checkbox' checked='false'></input>
                Enable pomodoro (experimental) </label>

            <hr style='margin-top: 1em;' />

            <center style='font-size:80%'>Static settings</center>
            <h2><i class='fas'>\uf0ac</i>&nbsp;&nbsp;Time zone</h2>
            <div></div>
            <h2><i class='fas'>\uf11c</i>&nbsp;&nbsp;Keyboard shortcuts</h2>
            <div class='formlayout'>{shortcuts_html}</div>
            <br /><br />
            """

        self.maindiv.innerHTML = html
        self._close_but = self.maindiv.children[0].children[-1]
        self._close_but.onclick = self.close
        (
            _,  # Dialog title
            _,  # Section: user settings
            _,  # Time repr header
            self._repr_form,
            _,  # Misc header
            self._tag_form,
            self._stopwatch_label,
            _,  # hr
            _,  # Section: per device
            _,  # Appearance header
            self._appearance_form,
            _,  # Notification header
            self._notification_label,
            _,  # Pomodoro header
            self._pomodoro_label,
            _,  # hr
            _,  # Section: info
            _,  # Timezone header
            self._timezone_div,
            _,  # Shortcuts header
            self._shortcuts_div,
        ) = self.maindiv.children

        # User settings

        # Weeks starts on
        first_day_of_week = window.simplesettings.get("first_day_of_week")
        self._first_day_of_week = self._repr_form.children[1]
        self._first_day_of_week.value = first_day_of_week
        self._first_day_of_week.onchange = self._on_first_day_of_week_change

        # Workdays
        workdays = window.simplesettings.get("workdays")
        self._workdays = self._repr_form.children[3]
        self._workdays.value = workdays
        self._workdays.onchange = self._on_workdays_change

        # Date representation
        date_repr = window.simplesettings.get("date_repr")
        self._date_repr = self._repr_form.children[5]
        self._date_repr.value = date_repr
        self._date_repr.onchange = self._on_date_repr_change

        # Time representation
        time_repr = window.simplesettings.get("time_repr")
        self._time_repr = self._repr_form.children[7]
        self._time_repr.value = time_repr
        self._time_repr.onchange = self._on_time_repr_change

        # Duration representation
        duration_repr = window.simplesettings.get("duration_repr")
        self._duration_repr = self._repr_form.children[9]
        self._duration_repr.value = duration_repr
        self._duration_repr.onchange = self._on_duration_repr_change

        # Today snap time/offset
        today_snap_offset = window.simplesettings.get("today_snap_offset")
        self._today_snap_offset = self._repr_form.children[11]
        self._today_snap_offset.value = today_snap_offset
        self._today_snap_offset.onchange = self._on_today_snap_offset_change

        # Today number of hours
        today_end_offset = window.simplesettings.get("today_end_offset")
        self._today_end_offset = self._repr_form.children[13]
        self._today_end_offset.value = today_end_offset
        self._today_end_offset.onchange = self._on_today_end_offset_change

        # Tag color
        tag_color = window.simplesettings.get("tag_color")
        self._tag_color = self._tag_form.children[1]
        self._tag_color.value = tag_color
        self._tag_color.onchange = self._on_tag_color_change

        # Stopwatch
        show_stopwatch = window.simplesettings.get("show_stopwatch")
        self._stopwatch_check = self._stopwatch_label.children[0]
        self._stopwatch_check.checked = show_stopwatch
        self._stopwatch_check.onchange = self._on_stopwatch_check

        # Device settings

        # Dark mode
        darkmode = window.simplesettings.get("darkmode")
        self._darkmode_select = self._appearance_form.children[1]
        self._darkmode_select.value = darkmode
        self._darkmode_select.onchange = self._on_darkmode_change

        # Width mode
        width_mode = window.simplesettings.get("width_mode")
        self._width_mode_select = self._appearance_form.children[3]
        self._width_mode_select.value = width_mode
        self._width_mode_select.onchange = self._on_width_mode_change

        # Notifications
        notifications_enabled = window.simplesettings.get("notifications")
        self._notification_check = self._notification_label.children[0]
        self._notification_check.checked = notifications_enabled
        self._notification_check.onchange = self._on_notifications_check

        # Pomodoro
        pomo_enabled = window.simplesettings.get("pomodoro_enabled")
        self._pomodoro_check = self._pomodoro_label.children[0]
        self._pomodoro_check.checked = pomo_enabled
        self._pomodoro_check.onchange = self._on_pomodoro_check

        # Static settings

        # Set timezone info
        self._timezone_div.innerText = "UTC" + dt.get_timezone_indicator(dt.now(), ":")

        super().open(callback)

    def _on_first_day_of_week_change(self):
        first_day_of_week = int(self._first_day_of_week.value)
        window.simplesettings.set("first_day_of_week", first_day_of_week)

    def _on_workdays_change(self):
        workdays = int(self._workdays.value)
        window.simplesettings.set("workdays", workdays)

    def _on_date_repr_change(self):
        date_repr = self._date_repr.value
        window.simplesettings.set("date_repr", date_repr)

    def _on_time_repr_change(self):
        time_repr = self._time_repr.value
        window.simplesettings.set("time_repr", time_repr)

    def _on_duration_repr_change(self):
        duration_repr = self._duration_repr.value
        window.simplesettings.set("duration_repr", duration_repr)

    def _on_today_snap_offset_change(self):
        today_snap_offset = self._today_snap_offset.value
        window.simplesettings.set("today_snap_offset", today_snap_offset)

    def _on_today_end_offset_change(self):
        today_end_offset = self._today_end_offset.value
        window.simplesettings.set("today_end_offset", today_end_offset)

    def _on_darkmode_change(self):
        darkmode = int(self._darkmode_select.value)
        window.simplesettings.set("darkmode", darkmode)
        if window.front:
            window.front.set_colors()

    def _on_width_mode_change(self):
        width_mode = self._width_mode_select.value
        window.simplesettings.set("width_mode", width_mode)
        if window.front:
            window.front.set_width_mode(width_mode)
            self._canvas._on_js_resize_event()  # private method, but ah well

    def _on_notifications_check(self):
        notifications_enabled = bool(self._notification_check.checked)
        window.simplesettings.set("notifications", notifications_enabled)
        # Ask the user
        if notifications_enabled:
            if window.Notification and window.Notification.permission == "default":
                Notification.requestPermission()

    def _on_pomodoro_check(self):
        pomo_enabled = bool(self._pomodoro_check.checked)
        window.simplesettings.set("pomodoro_enabled", pomo_enabled)

    def _on_stopwatch_check(self):
        show_stopwatch = bool(self._stopwatch_check.checked)
        window.simplesettings.set("show_stopwatch", show_stopwatch)

    def _on_tag_color_change(self):
        tag_color = self._tag_color.value
        window.simplesettings.set("tag_color", tag_color)


class GuideDialog(BaseDialog):
    """Dialog to have quick access to the guide."""

    def __init__(self, canvas):
        super().__init__(canvas)
        self.initialized = 0

    def open(self, callback=None):
        # Only init once, so that the guide stays in the state as the
        # user tries something and then opens it again. Up to 24 hours.
        if dt.now() < self.initialized + 86400:
            return super().open(callback)
        self.initialized = dt.now()

        self.maindiv.innerHTML = """
            <h1><i class='fas'>\uf05a</i>&nbsp;&nbsp;Guide
                <button type='button'><i class='fas'>\uf00d</i></button>
            </h1>
            <iframe src='https://timetagger.app/guide_headless'
            display:block; style='width:100%; height:calc(90vh - 100px); border:none;'
            />
        """

        self._cancel_but = self.maindiv.children[0].children[-1]
        self._cancel_but.onclick = self.close
        super().open(callback)


class PomodoroDialog(BaseDialog):
    """Dialog to control the Pomodoro timer."""

    def __init__(self, canvas):
        super().__init__(canvas)

        # Note that we assume that this is the only code touching the document title
        self._original_title = window.document.title

        # Init
        self._init()
        self._set_state("pre-work")

        # Setup callbacks
        window.setInterval(self._update, 250)
        window.document.addEventListener("visibilitychange", self._update)
        if window.navigator.serviceWorker:
            try:
                window.navigator.serviceWorker.addEventListener(
                    "message", self.on_notificationclick
                )
            except Exception:
                pass

        # Prepare sounds
        self._sounds = {
            "wind": Audio("wind-up-1-534.ogg"),
            "work_end": Audio("eventually-590.ogg"),
            "break_end": Audio("eventually-590.ogg"),
            "manual_end": Audio("clearly-602.ogg"),
        }

    def _init(self):
        html = f"""
            <h1><i class='fas'>\uf2f2</i>&nbsp;&nbsp;Pomodoro
                <button type='button'><i class='fas'>\uf00d</i></button>
            </h1>
            <center>
                <div style='margin: 1em; font-size: 140%;'>25:00</div>
                <button type='button' class='actionbutton' style='margin: 1em;'>Start</button>
            </center>
            <details style='color: #777; margin: 1em; font-size: 87%;'>
            <summary style='cursor: pointer;'>The Pomodoro Technique</summary>
            <p>
            The Pomodoro Technique is a time management method where you
            alternate between 25 minutes of work and 5 minute breaks.
            It is recommended to use breaks to leave your chair if you
            sit during work. See
            <a href='https://timetagger.app/pomodoro/' target='new'>this article</a>
            for more info.
            </p><p>
            The Pomodoro timer is automatically started and stopped as you
            start/stop tracking time. This feature is experimental - do
            let us know about problems and suggestions!
            </p><p>
            Using sounds from notificationsounds.com.
            </p></details>
            """

        self.maindiv.innerHTML = html

        self._close_but = self.maindiv.children[0].children[-1]
        self._close_but.onclick = self.close
        (
            self._label,
            self._button,
        ) = self.maindiv.children[1].children

        self._button.onclick = self._on_button_click

    def open(self, callback=None):
        super().open(callback)
        self._update()

    def _play_sound(self, sound):
        audio = self._sounds[sound]
        if audio.currentTime:
            audio.currentTime = 0
        promise = audio.play()
        # Catch when playing the sound failed, to avoid "nhandled Promise Rejection"
        if promise:
            promise.catch(lambda err: None)

    def _set_state(self, state):
        if state == "pre-work":
            etime = 0
            pretitle = ""
            self._button.innerHTML = "Start working"
        elif state == "work":
            etime = dt.now() + 25 * 60
            pretitle = "Working | "
            self._button.innerHTML = "Stop"
        elif state == "pre-break":
            etime = 0
            pretitle = ""
            self._button.innerHTML = "Start break"
        elif state == "break":
            etime = dt.now() + 5 * 60
            pretitle = "Break | "
            self._button.innerHTML = "Stop"
        else:
            console.warn("Invalid pomodoro state: " + state)
            return
        window.document.title = pretitle + self._original_title
        self._state = state, etime
        self._update()

    def time_left(self):
        etime = self._state[1]
        left = max(0, etime - dt.now())
        if left:
            return self._state[0] + ": " + dt.duration_string(left, True)
        else:
            return None

    def start_work(self):
        self._set_state("work")

        # Now is a good time to ask for permission,
        # assuming that this call originally came from a user's mouse click.
        if window.Notification and window.Notification.permission == "default":
            Notification.requestPermission()

        self._play_sound("wind")

    def stop(self):
        self._set_state("pre-work")

    def _on_button_click(self):
        state, etime = self._state
        if state == "pre-work":
            self.start_work()
        elif state == "work":
            self._set_state("pre-break")
            self._play_sound("manual_end")
        elif state == "pre-break":
            self._set_state("break")
            self._play_sound("wind")
        elif state == "break":
            self._set_state("pre-work")
            self._play_sound("manual_end")
        else:
            self._set_state("pre-work")

    def _update(self):
        # Always do this

        state, etime = self._state
        left = max(0, etime - dt.now())

        if state == "work":
            if not left:
                self._set_state("pre-break")
                self.alarm(state)
        elif state == "break":
            if not left:
                self._set_state("pre-work")
                self.alarm(state)

        # Exit early if we're not shown
        if window.document.hidden or not self.is_shown():
            return

        # Update GUI
        if state == "pre-work":
            self._label.innerHTML = "Work (25:00)"
        elif state == "work":
            self._label.innerHTML = "Working: " + dt.duration_string(left, True)
        elif state == "pre-break":
            self._label.innerHTML = "Break (5:00)"
        elif state == "break":
            self._label.innerHTML = "Break: " + dt.duration_string(left, True)
        else:
            self._set_state("pre-work")

    def alarm(self, old_state):
        # Open this dialog
        self.open()

        # Make a sound
        if old_state == "work":
            self._play_sound("work_end")
        elif old_state == "break":
            self._play_sound("break_end")

        # The window title is changed on _set_state, causing a blue dot
        # to appear when pinned. This is also part of the "alarm".

        # Show a system notification
        if window.Notification and Notification.permission == "granted":
            if old_state == "break":
                title = "Break is over, back to work!"
                actions = [
                    {"action": "work", "title": "Start 25m work"},
                    {"action": "close", "title": "Close"},
                ]
            elif old_state == "work":
                title = "Time for a break!"
                actions = [
                    {"action": "break", "title": "Start 5m break"},
                    {"action": "close", "title": "Close"},
                ]
            else:
                title = "Pomodoro"
                actions = []

            options = {
                "icon": "timetagger192_sf.png",
                "body": "Click to open TimeTagger",
                "requireInteraction": True,
                "tag": "timetagger-pomodoro",  # replace previous notifications
            }
            # If we show the notification via the service worker, we
            # can show actions, making the flow easier for users.
            if window.pwa and window.pwa.sw_reg:
                options.actions = actions
                window.pwa.sw_reg.showNotification(title, options)
            else:
                Notification(title, options)

    def on_notificationclick(self, message_event):
        """This is a callback for service worker events.
        We filter on 'notificationclick' types (defined by us).
        """
        event = message_event.data
        if event.type != "notificationclick":
            return
        if not window.simplesettings.get("pomodoro_enabled"):
            return
        if event.action == "work":
            self._set_state("work")
            self._play_sound("wind")
        elif event.action == "break":
            self._set_state("break")
            self._play_sound("wind")
