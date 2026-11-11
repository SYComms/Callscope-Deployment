"""
Call Scope onboarding documents (A4 PDFs).

Three documents are built from one dictionary of customer details:
  - build_manager_pack(d)  : every login, for the main contact only
  - build_staff_guide(d)   : the staff portal only - safe to forward to everyone
  - build_login_cards(d)   : one cut-out card per extension

Colours and wording live at the top so they are easy to change.
"""
import io
from xml.sax.saxutils import escape  # noqa: F401  (kept for callers)

from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

W, H = A4
M = 46                      # page margin
CW = W - 2 * M              # content width

NAVY = HexColor("#0A0E1A")
NAVY_2 = HexColor("#161F33")
INDIGO = HexColor("#5B63F5")
INDIGO_SOFT = HexColor("#ECEDFF")
CYAN = HexColor("#38D6F5")
TEXT = HexColor("#1B2333")
MUTED = HexColor("#5E6A82")
FAINT = HexColor("#8C98B0")
CARD = HexColor("#F5F7FC")
BORDER = HexColor("#DFE4F0")
GOOD = HexColor("#0E9F6E")
GOOD_SOFT = HexColor("#E3F7EF")
AMBER = HexColor("#B45309")
AMBER_SOFT = HexColor("#FDF1DC")

REG, BOLD, MONO = "Helvetica", "Helvetica-Bold", "Courier-Bold"


def _lerp(c1, c2, t):
    return Color(c1.red + (c2.red - c1.red) * t,
                 c1.green + (c2.green - c1.green) * t,
                 c1.blue + (c2.blue - c1.blue) * t)


def _gradient(c, x, y, w, h, c1=INDIGO, c2=CYAN, steps=80):
    sw = w / steps
    for i in range(steps):
        c.setFillColor(_lerp(c1, c2, i / (steps - 1)))
        c.rect(x + i * sw, y, sw + 0.6, h, stroke=0, fill=1)


def _fit(c, text, font, size, max_w, min_size=6.5):
    while size > min_size and c.stringWidth(text, font, size) > max_w:
        size -= 0.25
    return size


class Doc:
    """Small page/cursor helper around a ReportLab canvas."""

    def __init__(self, d, title, subtitle, confidential):
        self.d = d
        self.title = title
        self.subtitle = subtitle
        self.confidential = confidential
        self.buf = io.BytesIO()
        self.c = canvas.Canvas(self.buf, pagesize=A4)
        self.c.setTitle(f"{d['brand']} - {title} - {d['company']}")
        self.c.setAuthor(d["brand"])
        self.page = 0
        self.y = 0
        self.new_page(first=True)

    # ---- page furniture -------------------------------------------------
    def new_page(self, first=False):
        if self.page:
            self.c.showPage()
        self.page += 1
        if first:
            self._hero()
        else:
            self._slim_header()
        self._footer()

    def _hero(self):
        c, d = self.c, self.d
        bh = 178
        c.setFillColor(NAVY)
        c.rect(0, H - bh, W, bh, stroke=0, fill=1)
        # soft glows
        c.saveState()
        p = c.beginPath()
        p.rect(0, H - bh, W, bh)
        c.clipPath(p, stroke=0, fill=0)
        c.setFillColor(INDIGO); c.setFillAlpha(0.22)
        c.circle(W - 70, H - 20, 150, stroke=0, fill=1)
        c.setFillColor(CYAN); c.setFillAlpha(0.10)
        c.circle(W - 190, H - bh - 30, 120, stroke=0, fill=1)
        c.restoreState()
        _gradient(c, 0, H - bh - 4, W, 4)

        # brand row
        logo = d.get("logo_path")
        x = M
        top = H - 42
        if logo:
            try:
                c.drawImage(logo, M, top - 8, height=26, width=120, preserveAspectRatio=True,
                            anchor="sw", mask="auto")
            except Exception:
                logo = None
        if not logo:
            _gradient(c, M, top - 6, 22, 22, steps=20)
            c.setFillColor(NAVY)
            c.setFont(BOLD, 12)
            c.drawCentredString(M + 11, top + 1, d["brand"][:1].upper())
            c.setFillColor(white)
            c.setFont(BOLD, 12.5)
            c.drawString(M + 31, top + 1, d["brand"])
        c.setFillColor(CYAN)
        c.setFont(BOLD, 7.5)
        c.drawRightString(W - M, top + 2, "CUSTOMER ONBOARDING", charSpace=1.6)

        c.setFillColor(white)
        size = _fit(c, self.title, BOLD, 29, CW)
        c.setFont(BOLD, size)
        c.drawString(M, H - 104, self.title)
        c.setFillColor(HexColor("#B8C1D9"))
        c.setFont(REG, 12)
        c.drawString(M, H - 126, self.subtitle)

        # meta row
        c.setFont(BOLD, 6.8)
        c.setFillColor(HexColor("#7F8BA6"))
        cols = [("PREPARED FOR", d["company"])]
        if self.confidential and d.get("contact_name"):
            cols.append(("ATTENTION", d["contact_name"]))
        cols.append(("DATE", d["date_str"]))
        xx = M
        for label, val in cols:
            c.setFont(BOLD, 6.8); c.setFillColor(HexColor("#7F8BA6"))
            c.drawString(xx, H - 151, label, charSpace=1.1)
            c.setFont(BOLD, 9.5); c.setFillColor(white)
            c.drawString(xx, H - 164, val[:44])
            xx += max(130, c.stringWidth(val[:44], BOLD, 9.5) + 34)
        self.y = H - bh - 4 - 24

    def _slim_header(self):
        c, d = self.c, self.d
        c.setFillColor(NAVY)
        c.rect(0, H - 40, W, 40, stroke=0, fill=1)
        _gradient(c, 0, H - 43, W, 3)
        c.setFillColor(white); c.setFont(BOLD, 10)
        c.drawString(M, H - 25, d["brand"])
        c.setFillColor(HexColor("#B8C1D9")); c.setFont(REG, 9)
        c.drawRightString(W - M, H - 25, f"{self.title}  |  {d['company']}")
        self.y = H - 43 - 30

    def _footer(self):
        c, d = self.c, self.d
        c.setStrokeColor(BORDER); c.setLineWidth(0.7)
        c.line(M, 40, W - M, 40)
        c.setFont(REG, 7.6); c.setFillColor(FAINT)
        bits = [d["brand"]] + [b for b in (d.get("support_email"), d.get("support_phone"), d.get("website")) if b]
        c.drawString(M, 27, "   |   ".join(bits))
        c.drawRightString(W - M, 27, f"Page {self.page}")
        if self.confidential:
            c.setFont(BOLD, 6.6); c.setFillColor(AMBER)
            c.drawCentredString(W / 2, 14, "CONFIDENTIAL - CONTAINS LOGIN DETAILS - PLEASE DO NOT FORWARD", charSpace=0.8)

    def need(self, h):
        if self.y - h < 50:
            self.new_page()

    # ---- content blocks -------------------------------------------------
    def para(self, text, size=10, color=TEXT, font=REG, leading=None, width=None, x=None, gap=10):
        c = self.c
        leading = leading or size * 1.5
        width = width or CW
        x = M if x is None else x
        lines = simpleSplit(text, font, size, width)
        self.need(len(lines) * leading + gap)
        c.setFont(font, size); c.setFillColor(color)
        for ln in lines:
            c.drawString(x, self.y - size, ln)
            self.y -= leading
        self.y -= gap

    def heading(self, text, sub=None):
        self.need(70)
        c = self.c
        _gradient(c, M, self.y - 13, 3.5, 15, steps=6)
        c.setFont(BOLD, 14); c.setFillColor(TEXT)
        c.drawString(M + 11, self.y - 11, text)
        self.y -= 22
        if sub:
            self.para(sub, size=9.2, color=MUTED, gap=6)
        else:
            self.y -= 4

    def chip(self, x_right, y, text, fg, bg):
        c = self.c
        w = c.stringWidth(text, BOLD, 6.8) + len(text) * 0.7 + 14
        c.setFillColor(bg)
        c.roundRect(x_right - w, y, w, 14, 7, stroke=0, fill=1)
        c.setFillColor(fg); c.setFont(BOLD, 6.8)
        c.drawString(x_right - w + 7, y + 4.3, text, charSpace=0.7)

    def field(self, x, y, w, label, value, mono=True, link=None):
        """Labelled value box; y is the top of the label."""
        c = self.c
        c.setFont(BOLD, 6.5); c.setFillColor(FAINT)
        c.drawString(x, y - 6.5, label.upper(), charSpace=0.9)
        by = y - 33
        c.setFillColor(white); c.setStrokeColor(BORDER); c.setLineWidth(0.8)
        c.roundRect(x, by, w, 22, 5, stroke=1, fill=1)
        font = MONO if mono else BOLD
        size = _fit(c, value, font, 11, w - 18)
        c.setFont(font, size)
        c.setFillColor(INDIGO if link else TEXT)
        c.drawString(x + 9, by + 7, value)
        if link:
            c.linkURL(link, (x, by, x + w, by + 22), relative=0)

    def portal_card(self, num, title, chip_text, chip_tone, desc, url, creds, bullets):
        """creds: list of (label, value) shown side by side under the web address."""
        c = self.c
        tw = CW - 36
        desc_lines = simpleSplit(desc, REG, 9, tw - 150)
        bl = []
        for b in bullets:
            bl.append(simpleSplit(b, REG, 8.8, tw - 14))
        h = 18 + 30 + len(desc_lines) * 12.5 + 8 + 40 + (44 if creds else 0) \
            + (16 + sum(len(x) for x in bl) * 12 if bl else 0) + 12
        self.need(h + 14)
        top = self.y
        c.setFillColor(CARD); c.setStrokeColor(BORDER); c.setLineWidth(0.8)
        c.roundRect(M, top - h, CW, h, 10, stroke=1, fill=1)
        x = M + 18
        y = top - 18
        # badge + title
        c.setFillColor(INDIGO_SOFT)
        c.roundRect(x, y - 24, 26, 24, 6, stroke=0, fill=1)
        c.setFillColor(INDIGO); c.setFont(BOLD, 10)
        c.drawCentredString(x + 13, y - 16, num)
        c.setFillColor(TEXT); c.setFont(BOLD, 13)
        c.drawString(x + 36, y - 16.5, title)
        fg, bg = {"amber": (AMBER, AMBER_SOFT), "good": (GOOD, GOOD_SOFT)}.get(chip_tone, (INDIGO, INDIGO_SOFT))
        self.chip(M + CW - 18, y - 19, chip_text.upper(), fg, bg)
        y -= 30
        c.setFont(REG, 9); c.setFillColor(MUTED)
        for ln in desc_lines:
            c.drawString(x + 36, y - 8, ln)
            y -= 12.5
        y -= 8
        self.field(x, y, tw, "Web address", url, link=url)
        y -= 40
        if creds:
            gap = 12
            fw = (tw - gap * (len(creds) - 1)) / len(creds)
            for i, (label, value) in enumerate(creds):
                self.field(x + i * (fw + gap), y, fw, label, value)
            y -= 44
        if bl:
            c.setFont(BOLD, 6.5); c.setFillColor(FAINT)
            c.drawString(x, y - 6.5, "WHAT YOU'LL FIND", charSpace=0.9)
            y -= 16
            for lines in bl:
                c.setFillColor(INDIGO)
                c.circle(x + 3, y - 5.2, 1.7, stroke=0, fill=1)
                c.setFont(REG, 8.8); c.setFillColor(TEXT)
                for ln in lines:
                    c.drawString(x + 12, y - 8, ln)
                    y -= 12
        self.y = top - h - 14

    def callout(self, title, text, tone="indigo"):
        c = self.c
        fg, bg = {"amber": (AMBER, AMBER_SOFT), "good": (GOOD, GOOD_SOFT)}.get(tone, (INDIGO, INDIGO_SOFT))
        lines = simpleSplit(text, REG, 9.2, CW - 40)
        h = 14 + 14 + len(lines) * 13 + 8
        self.need(h + 10)
        top = self.y
        c.setFillColor(bg)
        c.roundRect(M, top - h, CW, h, 9, stroke=0, fill=1)
        c.setFillColor(fg)
        c.roundRect(M, top - h, 4, h, 2, stroke=0, fill=1)
        c.setFont(BOLD, 10)
        c.drawString(M + 20, top - 22, title)
        c.setFont(REG, 9.2); c.setFillColor(TEXT)
        y = top - 37
        for ln in lines:
            c.drawString(M + 20, y, ln)
            y -= 13
        self.y = top - h - 10

    def formula(self, slug, example_ext, pattern):
        """Visual: [slug] + [your extension] = password"""
        c = self.c
        h = 78
        self.need(h + 12)
        top = self.y
        c.setFillColor(NAVY)
        c.roundRect(M, top - h, CW, h, 10, stroke=0, fill=1)
        c.setFont(BOLD, 6.8); c.setFillColor(CYAN)
        c.drawString(M + 20, top - 22, "HOW EVERY STAFF PASSWORD IS MADE", charSpace=1.2)
        y = top - 58
        x = M + 20

        def pill(x, text, sub, fill, fg, font=MONO):
            w = max(c.stringWidth(text, font, 13) + 26, c.stringWidth(sub, BOLD, 6.2) + 26)
            c.setFillColor(fill)
            c.roundRect(x, y, w, 28, 7, stroke=0, fill=1)
            c.setFillColor(fg); c.setFont(font, 13)
            c.drawCentredString(x + w / 2, y + 9.5, text)
            c.setFont(BOLD, 6.2); c.setFillColor(HexColor("#7F8BA6"))
            c.drawCentredString(x + w / 2, y - 10, sub.upper())
            return x + w

        def op(x, s):
            c.setFillColor(white); c.setFont(BOLD, 15)
            c.drawCentredString(x + 13, y + 9, s)
            return x + 26

        example_pw = pattern.replace("{slug}", slug).replace("{ext}", example_ext)
        x = pill(x, slug, "your site name", NAVY_2, white)
        x = op(x, "+")
        x = pill(x, example_ext, "your extension", NAVY_2, white)
        x = op(x, "=")
        x = pill(x, example_pw, "your password", CYAN, NAVY)
        self.y = top - h - 12

    def step(self, n, title, lines, value=None, link=None):
        c = self.c
        body = []
        for ln in lines:
            body += simpleSplit(ln, REG, 9.6, CW - 78)
        h = 18 + 16 + len(body) * 13.5 + (36 if value else 0) + 6
        self.need(h + 9)
        top = self.y
        c.setFillColor(CARD); c.setStrokeColor(BORDER); c.setLineWidth(0.8)
        c.roundRect(M, top - h, CW, h, 10, stroke=1, fill=1)
        _gradient(c, M + 18, top - 46, 28, 28, steps=24)
        c.setFillColor(NAVY); c.setFont(BOLD, 14)
        c.drawCentredString(M + 32, top - 37, str(n))
        x = M + 60
        c.setFillColor(TEXT); c.setFont(BOLD, 12.5)
        c.drawString(x, top - 30, title)
        y = top - 48
        c.setFont(REG, 9.6); c.setFillColor(MUTED)
        for ln in body:
            c.drawString(x, y, ln)
            y -= 13.5
        if value:
            by = y - 22
            w = CW - 78
            c.setFillColor(white); c.setStrokeColor(BORDER)
            c.roundRect(x, by, w, 24, 5, stroke=1, fill=1)
            size = _fit(c, value, MONO, 12, w - 18)
            c.setFont(MONO, size); c.setFillColor(INDIGO if link else TEXT)
            c.drawString(x + 9, by + 8, value)
            if link:
                c.linkURL(link, (x, by, x + w, by + 24), relative=0)
        self.y = top - h - 9

    def bullets(self, items, size=9.4):
        c = self.c
        for it in items:
            lines = simpleSplit(it, REG, size, CW - 16)
            self.need(len(lines) * size * 1.45 + 4)
            c.setFillColor(INDIGO)
            c.circle(M + 3, self.y - size * 0.62, 1.9, stroke=0, fill=1)
            c.setFont(REG, size); c.setFillColor(TEXT)
            for ln in lines:
                c.drawString(M + 14, self.y - size, ln)
                self.y -= size * 1.45
            self.y -= 3
        self.y -= 4

    def ext_table(self, exts, show_pw):
        """Compact multi-column table of extension logins."""
        c = self.c
        has_names = any(n for _, n, _ in exts)
        ncols = 2 if has_names else 3
        gap = 14
        cw = (CW - gap * (ncols - 1)) / ncols
        row_h = 15
        i = 0
        while i < len(exts):
            self.need(row_h * 4 + 20)
            avail_rows = int((self.y - 62 - 18) // row_h)
            chunk = exts[i:i + avail_rows * ncols]
            rows = -(-len(chunk) // ncols)
            top = self.y
            for col in range(ncols):
                x = M + col * (cw + gap)
                part = chunk[col * rows:(col + 1) * rows]
                if not part:
                    continue
                c.setFillColor(NAVY)
                c.roundRect(x, top - 16, cw, 16, 4, stroke=0, fill=1)
                c.setFillColor(white); c.setFont(BOLD, 6.8)
                c.drawString(x + 8, top - 11, "USERNAME", charSpace=0.8)
                if has_names:
                    c.drawString(x + 62, top - 11, "NAME", charSpace=0.8)
                c.drawString(x + cw - (92 if has_names else cw - 78), top - 11, "PASSWORD", charSpace=0.8)
                y = top - 16
                for r, (ext, name, pw) in enumerate(part):
                    if r % 2 == 0:
                        c.setFillColor(CARD)
                        c.rect(x, y - row_h, cw, row_h, stroke=0, fill=1)
                    c.setFillColor(TEXT); c.setFont(MONO, 9)
                    c.drawString(x + 8, y - 10.5, ext)
                    if has_names:
                        c.setFont(REG, 8.6)
                        nm = name or "-"
                        while c.stringWidth(nm, REG, 8.6) > cw - 62 - 100 and len(nm) > 3:
                            nm = nm[:-2]
                        c.drawString(x + 62, y - 10.5, nm if nm == (name or "-") else nm + "...")
                    c.setFont(MONO, _fit(c, pw, MONO, 9, 86 if has_names else cw - 84))
                    c.setFillColor(TEXT if show_pw else FAINT)
                    c.drawString(x + cw - (92 if has_names else cw - 78), y - 10.5, pw if show_pw else "see rule above")
                    y -= row_h
            self.y = top - 16 - rows * row_h - 16
            i += len(chunk)

    def help_box(self, lead):
        c, d = self.c, self.d
        h = 62
        self.need(h)
        top = self.y
        c.setFillColor(NAVY)
        c.roundRect(M, top - h, CW, h, 10, stroke=0, fill=1)
        _gradient(c, M, top - h, CW, 3)
        c.setFillColor(white); c.setFont(BOLD, 12)
        c.drawString(M + 20, top - 26, "Need a hand?")
        c.setFont(REG, 9.2); c.setFillColor(HexColor("#B8C1D9"))
        c.drawString(M + 20, top - 42, lead)
        bits = [b for b in (d.get("support_email"), d.get("support_phone")) if b]
        c.setFillColor(CYAN); c.setFont(BOLD, 10)
        yy = top - 26 if len(bits) > 1 else top - 34
        for b in bits:
            c.drawRightString(M + CW - 20, yy, b)
            yy -= 16
        self.y = top - h - 14

    def finish(self):
        self.c.save()
        return self.buf.getvalue()


# ---------------------------------------------------------------------------
def _example(d):
    exts = d.get("exts") or []
    ext = exts[0][0] if exts else "1000"
    return ext, d["pw_pattern"].replace("{slug}", d["slug"]).replace("{ext}", ext)


def build_manager_pack(d):
    show = d.get("show_passwords", True)
    hidden = "Sent separately"
    doc = Doc(d, f"Welcome to {d['brand']}", "Your access pack - everything you need to get started", True)
    first = (d.get("contact_name") or "").split(" ")[0]
    doc.para(f"Hi {first}," if first else "Hello,", size=11.5, font=BOLD, gap=4)
    n_portals = 3 if d.get("mgr_url") else 2
    doc.para(
        f"Your {d['brand']} service for {d['company']} is live. You have {'three' if n_portals == 3 else 'two'} "
        f"places to log in, each built for a different job. This pack is for you as the main contact - it holds the "
        f"administrator details, so please keep it to yourself. A separate Staff Guide is included that is safe to "
        f"share with your whole team.", size=10, color=MUTED, gap=14)

    doc.heading("Your logins")
    n = 1
    doc.portal_card(
        f"{n:02d}", d["rec_title"], "Admin only", "amber", d["rec_desc"], d["rec_url"],
        [("Username", d["rec_user"]), ("Password", d["rec_pass"] if show else hidden)], d["rec_bullets"])
    if d.get("mgr_url"):
        n += 1
        creds = []
        if d.get("mgr_user"):
            creds.append(("Username", d["mgr_user"]))
        creds.append(("Password", d["mgr_pass"] if show else hidden))
        doc.portal_card(f"{n:02d}", d["mgr_title"], "Managers", "indigo", d["mgr_desc"], d["mgr_url"],
                        creds, d["mgr_bullets"])
    n += 1
    ext, pw = _example(d)
    doc.portal_card(
        f"{n:02d}", d["ai_title"], "All staff", "good", d["ai_desc"], d["ai_url"],
        [("Username", "Their extension number"), ("Password", f"{d['slug']} + extension")], d["ai_bullets"])

    doc.heading("Getting your team started",
                "Every member of staff has their own login to the staff portal. There is nothing to set up - "
                "each login follows the same simple rule.")
    doc.formula(d["slug"], ext, d["pw_pattern"])
    exts = d.get("exts") or []
    if exts and len(exts) <= d.get("table_limit", 180):
        doc.para(f"Your {len(exts)} staff logins", size=10.5, font=BOLD, gap=6)
        doc.ext_table(exts, show)
    elif exts:
        doc.para(f"Your site has {len(exts)} extensions ({exts[0][0]} to {exts[-1][0]}). Every one follows the rule above.",
                 size=9.6, color=MUTED)
    doc.callout("Sharing with your team",
                "Send the Staff Guide to your team - it only covers the staff portal and how each person works out "
                "their own login. Please keep this access pack private, as it contains the administrator"
                + (" and manager dashboard" if d.get("mgr_url") else "") + " details.", "amber")
    doc.help_box("We're here to help you get the most from your service.")
    return doc.finish()


def build_staff_guide(d, person=None):
    """person=(extension, name, password) makes a personal copy with that login filled in."""
    if person:
        ext, name, pw = person
        doc = Doc(d, f"Your {d['brand']} login", f"Personal login for {name}" if name else f"Personal login for extension {ext}", False)
        first = (name or "").split(" ")[0]
        doc.para(f"Hi {first}," if first else "Hello,", size=11.5, font=BOLD, gap=4)
        doc.para(f"{d['company']} now uses {d['brand']}, and your personal login is ready. "
                 f"It takes about a minute to get in - just follow the three steps below.", size=10.5, color=MUTED, gap=10)
        doc.step(1, "Open your portal", ["Go to this address in your web browser. It's worth saving as a bookmark."],
                 value=d["ai_url"], link=d["ai_url"])
        doc.step(2, "Enter your username", ["Your username is your extension number."], value=ext)
        doc.step(3, "Enter your password", ["Type it exactly as shown - all lower case, no spaces."], value=pw)
    else:
        doc = Doc(d, f"Your {d['brand']} login", f"Staff quick-start guide for {d['company']}", False)
        ext, pw = _example(d)
        doc.para(f"{d['company']} now uses {d['brand']}. You have your own personal login - it takes about a minute "
                 f"to get in. Just follow the three steps below.", size=10.5, color=MUTED, gap=10)
        doc.step(1, "Open your portal", ["Go to this address in your web browser. It's worth saving as a bookmark."],
                 value=d["ai_url"], link=d["ai_url"])
        doc.step(2, "Enter your username",
                 [f"Your username is your own extension number - for example {ext}.",
                  "Not sure what your extension is? Ask your manager."])
        doc.step(3, "Enter your password",
                 [f"Your password is the word \"{d['slug']}\" followed straight away by your extension number - "
                  f"all lower case, no spaces."])
        doc.formula(d["slug"], ext, d["pw_pattern"])
    if d.get("ai_bullets"):
        doc.heading("What you'll find inside")
        doc.bullets(d["ai_bullets"])
    doc.callout("Keep it personal", "Your login shows your own calls, so please don't share it with colleagues. "
                "If you have any trouble logging in, speak to your manager first.", "indigo")
    doc.help_box("Your manager can contact us at any time.")
    return doc.finish()


def build_login_cards(d):
    """Cut-out cards, 8 per A4 page."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"{d['brand']} - Staff login cards - {d['company']}")
    cols, rows = 2, 4
    gx, gy = 16, 14
    cw = (W - 2 * 34 - gx) / cols
    ch = (H - 2 * 34 - gy * (rows - 1)) / rows
    exts = d.get("exts") or []
    for i, (ext, name, pw) in enumerate(exts):
        k = i % (cols * rows)
        if i and k == 0:
            c.showPage()
        col, row = k % cols, k // cols
        x = 34 + col * (cw + gx)
        top = H - 34 - row * (ch + gy)
        c.setFillColor(white); c.setStrokeColor(FAINT); c.setLineWidth(0.6); c.setDash(3, 3)
        c.roundRect(x, top - ch, cw, ch, 10, stroke=1, fill=1)
        c.setDash()
        # header band
        c.saveState()
        p = c.beginPath(); p.roundRect(x + 1, top - ch + 1, cw - 2, ch - 2, 9)
        c.clipPath(p, stroke=0, fill=0)
        c.setFillColor(NAVY); c.rect(x, top - 48, cw, 48, stroke=0, fill=1)
        _gradient(c, x, top - 51, cw, 3)
        c.restoreState()
        c.setFillColor(CYAN); c.setFont(BOLD, 6.5)
        c.drawString(x + 16, top - 19, f"{d['brand'].upper()} LOGIN", charSpace=1.2)
        c.setFillColor(white)
        title = name or f"Extension {ext}"
        c.setFont(BOLD, _fit(c, title, BOLD, 13, cw - 32))
        c.drawString(x + 16, top - 37, title)
        y = top - 66
        for label, val, link in (("Web address", d["ai_url"], True), ("Username", ext, False), ("Password", pw, False)):
            c.setFont(BOLD, 6.2); c.setFillColor(FAINT)
            c.drawString(x + 16, y, label.upper(), charSpace=0.9)
            c.setFont(MONO, _fit(c, val, MONO, 10.5, cw - 32))
            c.setFillColor(INDIGO if link else TEXT)
            c.drawString(x + 16, y - 14, val)
            y -= 34
        c.setFont(REG, 6.8); c.setFillColor(FAINT)
        c.drawString(x + 16, top - ch + 12, f"{d['company']}  |  Personal login - please don't share")
    c.save()
    return buf.getvalue()
