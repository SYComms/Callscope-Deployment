"""
Call Scope Onboarding Manager
-----------------------------
Enter a new customer's Call Scope details, get a branded Access Pack (for the
main contact) and Staff Guide (safe to share), then email them from Zoho CRM
so the send is logged on the customer's account.

Secrets (Streamlit Cloud > Settings > Secrets):
    APP_PASSWORD        = "..."            # required
    ZOHO_CLIENT_ID      = "..."            # optional - enables the Zoho section
    ZOHO_CLIENT_SECRET  = "..."
    ZOHO_REFRESH_TOKEN  = "..."            # get it from the helper in the sidebar
"""
import csv
import datetime as dt
import hmac
import html as html_lib
import inspect
import io
import os
import re

import requests
import streamlit as st

import onboarding_pdf as pdfs

# ----------------------------------------------------------------------------
# Settings you may want to change
# ----------------------------------------------------------------------------
BRAND = "Call Scope"
SUPPORT_EMAIL = "hello@callscope.co.uk"
SUPPORT_PHONE = ""
WEBSITE = "callscope.co.uk"
EMAIL_SIGN_OFF = "The Call Scope Team"

DEFAULT_DOMAIN = "sycomms.cloud"        # customer sites live at https://<slug>.<domain>/
RECORDINGS_PATH = "/recordings/"
STAFF_PATH = "/ai/"
DEFAULT_MANAGER_PATH = ""               # e.g. "/dashboard/" - blank = type it in per customer
PW_PATTERN = "{slug}{ext}"              # staff password rule
MAX_EXTENSIONS = 2000
CARD_LIMIT = 400                        # most login cards we will lay out

DEFAULT_WORDING = {
    "rec_title": "Call Recordings",
    "rec_desc": "The administrator view of the recorded calls on your system.",
    "rec_bullets": "Search, play back and download call recordings\nFind calls by date, extension or phone number",
    "mgr_title": "Manager Dashboard",
    "mgr_desc": "Your at-a-glance view of how the whole team is handling calls.",
    "mgr_bullets": "Team-wide call statistics and trends\nSee busy periods and how calls are being handled",
    "ai_title": "Staff AI Portal",
    "ai_desc": "A personal login for each member of staff, using their own extension number.",
    "ai_bullets": "Your own calls, with AI summaries and insights\nA private view - you only see your own activity",
}

ZOHO_SCOPE = "ZohoCRM.modules.ALL,ZohoCRM.send_mail.all.CREATE,ZohoCRM.Files.CREATE,ZohoCRM.settings.emails.READ"

HERE = os.path.dirname(os.path.abspath(__file__))
LOGO_DARK = os.path.join(HERE, "callscope_logo_dark.png")   # white wording, for dark backgrounds (PDF headers)
LOGO_ICON = os.path.join(HERE, "callscope_icon.png")

st.set_page_config(page_title=f"{BRAND} Onboarding", page_icon=LOGO_ICON if os.path.exists(LOGO_ICON) else "📞",
                   layout="wide")


def _img_tag(path, height):
    try:
        import base64
        with open(path, "rb") as f:
            return f'<img src="data:image/png;base64,{base64.b64encode(f.read()).decode()}" style="height:{height}px" alt="Call Scope">'
    except Exception:
        return ""


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------
def sec(name, default=""):
    try:
        return st.secrets.get(name, default)
    except Exception:
        return default


def esc(v):
    return html_lib.escape(str(v if v is not None else ""), quote=True)


def render_html(markup, target=None):
    (target or st).markdown("".join(l.strip() for l in markup.splitlines()), unsafe_allow_html=True)


def chip(text, tone=""):
    return f'<span class="pe-chip {tone}">{esc(text)}</span>'


def section_header(num, title, subtitle=""):
    render_html(f'<div class="pe-section"><div class="badge">{num}</div><div><div class="t">{esc(title)}</div>'
                + (f'<div class="s">{esc(subtitle)}</div>' if subtitle else "") + "</div></div>")


def _full_width():
    try:
        if "width" in inspect.signature(st.button).parameters:
            return {"width": "stretch"}
    except (TypeError, ValueError):
        pass
    return {"use_container_width": True}


FULL_WIDTH = _full_width()

ICON_PHONE = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 '
              '19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 '
              '2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/></svg>')

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--bg:#0A0E1A;--surface:#111827;--surface-2:#161F33;--surface-3:#1C2740;--border:rgba(148,163,184,.14);--border-strong:rgba(148,163,184,.26);--text:#E7EAF3;--muted:#8C98B0;--faint:#5E6A82;--accent:#8B84F2;--accent-2:#B3ADF7;--accent-soft:rgba(121,113,234,.16);--good:#34D399;--warn:#FBBF24;--risk:#FB923C;--bad:#F87171;--radius:14px;--grad:linear-gradient(135deg,#7971EA 0%,#B3ADF7 100%);}
html,body,[class*="css"],.stApp,button,input,textarea,select{font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif!important}
.stApp{background:radial-gradient(1200px 500px at 85% -10%,rgba(179,173,247,.06),transparent 60%),radial-gradient(900px 500px at 10% -20%,rgba(121,113,234,.10),transparent 60%),var(--bg)}
[data-testid="stHeader"]{background:transparent}[data-testid="stDecoration"]{display:none}footer{visibility:hidden}
.block-container{padding-top:1.6rem!important;padding-bottom:3rem!important;max-width:1500px}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0D1322 0%,#0A0E1A 100%);border-right:1px solid var(--border)}
[data-testid="stWidgetLabel"] p{font-size:.76rem!important;font-weight:600!important;color:var(--muted)!important;text-transform:uppercase;letter-spacing:.06em}
[data-testid="stCaptionContainer"]{color:var(--muted)!important}
.st-key-card-customer,.st-key-card-portals,.st-key-card-users,.st-key-card-docs,.st-key-card-send,.st-key-card-summary,.st-key-card-login{background:linear-gradient(180deg,rgba(22,31,51,.85) 0%,rgba(17,24,39,.85) 100%);border:1px solid var(--border)!important;border-radius:var(--radius);padding:22px 22px 18px;box-shadow:0 1px 0 rgba(255,255,255,.03) inset,0 20px 40px -24px rgba(0,0,0,.6);margin-bottom:18px}
[data-testid="stColumn"]:has(.st-key-card-summary){position:sticky;top:1rem;align-self:flex-start}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{background:var(--surface)!important;border:1px solid var(--border-strong)!important;border-radius:10px!important}
[data-baseweb="input"]:focus-within,[data-baseweb="select"]>div:focus-within,[data-baseweb="textarea"]:focus-within{border-color:var(--accent)!important;box-shadow:0 0 0 3px var(--accent-soft)!important}
[data-baseweb="input"]>div,[data-baseweb="base-input"]{background:transparent!important}
.stButton button,.stDownloadButton button,.stFormSubmitButton button{border-radius:10px!important;font-weight:600!important;border:1px solid var(--border-strong)!important;background:var(--surface-2)!important;color:var(--text)!important;transition:all .15s ease}
.stButton button:hover,.stDownloadButton button:hover{border-color:var(--accent)!important;transform:translateY(-1px)}
.stButton button[kind="primary"],.stDownloadButton button[kind="primary"],.stFormSubmitButton button,[data-testid="stBaseButton-primary"],[data-testid="stBaseLinkButton-primary"]{background:var(--grad)!important;border:none!important;color:#0A0E1A!important;box-shadow:0 8px 24px -10px rgba(121,113,234,.8)}
.stButton button[kind="primary"] p,.stDownloadButton button[kind="primary"] p,[data-testid="stBaseButton-primary"] p,.stFormSubmitButton button p,[data-testid="stBaseLinkButton-primary"] p{color:#0A0E1A!important;font-weight:700!important}
[data-testid="stTabs"] [role="tablist"],[data-baseweb="tab-list"]{gap:4px;background:var(--surface);padding:4px;border-radius:12px;border:1px solid var(--border);width:fit-content}
[data-testid="stTabs"] [role="tab"],[data-baseweb="tab"]{border-radius:9px!important;padding:8px 16px!important;color:var(--muted)!important;background:transparent!important}
[data-testid="stTabs"] [role="tab"][aria-selected="true"],[data-baseweb="tab"][aria-selected="true"]{background:var(--surface-3)!important;color:var(--text)!important}
[data-baseweb="tab-highlight"],[data-baseweb="tab-border"],[data-testid="stTabs"] .react-aria-SelectionIndicator{display:none!important}
[data-testid="stExpander"] details{background:var(--surface);border:1px solid var(--border)!important;border-radius:12px!important}
[data-testid="stAlert"]{border-radius:12px!important}
.pe-hero{display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap;padding:6px 2px 22px;margin-bottom:18px;border-bottom:1px solid var(--border)}
.pe-eyebrow{display:inline-flex;align-items:center;gap:8px;font-size:.72rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--accent-2);margin-bottom:8px}
.pe-eyebrow .dot{width:7px;height:7px;border-radius:50%;background:var(--good);box-shadow:0 0 0 4px rgba(52,211,153,.15)}
.pe-title{font-size:2.05rem;font-weight:800;letter-spacing:-.035em;line-height:1.1;color:var(--text)}
.pe-title span{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.pe-sub{color:var(--muted);font-size:.95rem;margin-top:8px;max-width:620px}
.pe-stepper{display:flex;align-items:center;gap:6px;background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:6px}
.pe-step{display:flex;align-items:center;gap:8px;padding:7px 14px 7px 7px;border-radius:999px;font-size:.82rem;font-weight:600;color:var(--faint);white-space:nowrap}
.pe-step .num{width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font-size:.72rem;font-weight:700;border:1px solid var(--border-strong)}
.pe-step.done{color:var(--muted)}.pe-step.done .num{background:rgba(52,211,153,.14);border-color:rgba(52,211,153,.45);color:var(--good)}
.pe-step.active{background:var(--surface-3);color:var(--text)}.pe-step.active .num{background:var(--grad);border:none;color:#0A0E1A}
.pe-step-sep{width:14px;height:1px;background:var(--border-strong)}
.pe-section{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.pe-section .badge{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent);font-weight:800;font-size:.85rem;border:1px solid rgba(121,113,234,.3)}
.pe-section .t{font-size:1.08rem;font-weight:700;color:var(--text)}.pe-section .s{font-size:.82rem;color:var(--muted);margin-top:2px}
.pe-chip{display:inline-flex;align-items:center;gap:6px;padding:4px 10px;border-radius:999px;font-size:.76rem;font-weight:600;background:var(--surface-3);color:var(--text);border:1px solid var(--border);white-space:nowrap}
.pe-chip.accent{background:var(--accent-soft);color:#B9BDFF;border-color:rgba(121,113,234,.3)}
.pe-chip.good{background:rgba(52,211,153,.12);color:var(--good);border-color:rgba(52,211,153,.3)}
.pe-chip.warn{background:rgba(251,191,36,.12);color:var(--warn);border-color:rgba(251,191,36,.3)}
.pe-chip.bad{background:rgba(248,113,113,.12);color:var(--bad);border-color:rgba(248,113,113,.3)}
.pe-logo{width:40px;height:40px;border-radius:12px;background:var(--grad);display:grid;place-items:center;color:#0A0E1A;box-shadow:0 10px 24px -10px rgba(121,113,234,.9)}
.pe-login-head{text-align:center;margin:8vh 0 22px}.pe-login-head .pe-logo{width:54px;height:54px;margin:0 auto 16px;border-radius:16px}
.pe-login-head .t{font-size:1.6rem;font-weight:800;letter-spacing:-.03em;color:var(--text)}.pe-login-head .s{color:var(--muted);font-size:.92rem;margin-top:6px}
.pe-brand{display:flex;align-items:center;gap:12px;margin-bottom:18px}.pe-brand .n{font-weight:800;color:var(--text)}.pe-brand .g{font-size:.78rem;color:var(--muted)}
.pe-row{display:flex;justify-content:space-between;align-items:center;gap:10px;padding:9px 0;border-bottom:1px solid var(--border);font-size:.86rem;color:var(--muted)}
.pe-row:last-child{border-bottom:none}.pe-row b{color:var(--text);font-weight:600;text-align:right;word-break:break-all}
.pe-url{font-family:ui-monospace,Menlo,Consolas,monospace!important;font-size:.82rem;color:var(--accent-2);background:var(--surface);border:1px solid var(--border);border-radius:9px;padding:9px 12px;margin:-6px 0 12px;word-break:break-all}
.pe-empty{text-align:center;padding:26px 10px;color:var(--muted)}.pe-empty .ic{width:48px;height:48px;border-radius:14px;background:var(--accent-soft);color:var(--accent);display:grid;place-items:center;margin:0 auto 12px}
.pe-empty .t{font-weight:700;color:var(--text);margin-bottom:6px}.pe-empty ol{display:inline-block;text-align:left;font-size:.86rem;margin:0;padding-left:18px}
.pe-dot{width:8px;height:8px;border-radius:50%;display:inline-block;margin-right:8px}
[data-testid="stImage"] img{border-radius:10px;border:1px solid var(--border)}
"""
render_html(f"<style>{CSS}</style>")


# ----------------------------------------------------------------------------
# Password gate (fails closed if no password is set)
# ----------------------------------------------------------------------------
def gate():
    if st.session_state.get("authed"):
        return
    logo_html = _img_tag(LOGO_DARK, 58)
    render_html('<div class="pe-login-head">'
                + (f'<div style="margin-bottom:18px">{logo_html}</div>' if logo_html else f'<div class="pe-logo">{ICON_PHONE}</div>')
                + f'<div class="t">{"Onboarding Manager" if logo_html else esc(BRAND) + " Onboarding"}</div>'
                '<div class="s">Create and send customer welcome packs</div></div>')
    _, mid, _ = st.columns([1, 1.1, 1])
    with mid, st.container(key="card-login"):
        expected = str(sec("APP_PASSWORD", ""))
        if not expected:
            st.error("No APP_PASSWORD is set in Streamlit Secrets, so the app is locked.")
            st.stop()
        with st.form("login"):
            pw = st.text_input("Password", type="password")
            if st.form_submit_button("Log in", **FULL_WIDTH):
                if hmac.compare_digest(pw.encode(), expected.encode()):
                    st.session_state["authed"] = True
                    st.rerun()
                else:
                    st.error("That password isn't right.")
    st.stop()


gate()


# ----------------------------------------------------------------------------
# Zoho CRM (EU data centre by default)
# ----------------------------------------------------------------------------
ZOHO_ACCOUNTS = str(sec("ZOHO_ACCOUNTS_BASE", "https://accounts.zoho.eu")).rstrip("/")
ZOHO_API = str(sec("ZOHO_API_BASE", "https://www.zohoapis.eu")).rstrip("/") + "/crm/v8"
ZOHO_READY = bool(sec("ZOHO_CLIENT_ID") and sec("ZOHO_CLIENT_SECRET") and sec("ZOHO_REFRESH_TOKEN"))


class ZohoError(Exception):
    pass


@st.cache_data(ttl=3000, show_spinner=False)
def _access_token(client_id, client_secret, refresh_token):
    r = requests.post(f"{ZOHO_ACCOUNTS}/oauth/v2/token", timeout=30, data={
        "refresh_token": refresh_token, "client_id": client_id,
        "client_secret": client_secret, "grant_type": "refresh_token"})
    j = r.json() if r.content else {}
    if "access_token" not in j:
        raise ZohoError(f"Zoho would not issue a token: {j.get('error', r.status_code)}")
    return j["access_token"]


def zoho(method, path, **kw):
    token = _access_token(sec("ZOHO_CLIENT_ID"), sec("ZOHO_CLIENT_SECRET"), sec("ZOHO_REFRESH_TOKEN"))
    r = requests.request(method, f"{ZOHO_API}{path}", timeout=60,
                         headers={"Authorization": f"Zoho-oauthtoken {token}"}, **kw)
    if r.status_code == 204 or not r.content:
        return {}
    try:
        j = r.json()
    except ValueError:
        raise ZohoError(f"Zoho returned an unexpected reply ({r.status_code}).")
    if r.status_code >= 400:
        raise ZohoError(_zoho_msg(j) or f"Zoho error {r.status_code}")
    return j


def _zoho_msg(j):
    item = (j.get("data") or [j])[0] if isinstance(j, dict) else {}
    if isinstance(item, dict) and item.get("status") == "error" or item.get("code") not in (None, "SUCCESS"):
        detail = item.get("details") or {}
        extra = f" ({detail})" if detail else ""
        return f"{item.get('code', '')}: {item.get('message', '')}{extra}"
    return ""


def _check(j):
    msg = _zoho_msg(j)
    if msg:
        raise ZohoError(msg)
    return (j.get("data") or [{}])[0]


def zoho_search_accounts(q):
    q = re.sub(r"[(),\\]", " ", q).strip()
    j = zoho("GET", "/Accounts/search", params={
        "criteria": f"(Account_Name:starts_with:{q})", "fields": "Account_Name,Phone,Billing_City", "per_page": 15})
    return j.get("data", [])


def zoho_contacts(account_id):
    j = zoho("GET", f"/Accounts/{account_id}/Contacts",
             params={"fields": "Full_Name,First_Name,Last_Name,Email", "per_page": 50})
    return [c for c in j.get("data", []) if c.get("Email")]


@st.cache_data(ttl=600, show_spinner=False)
def zoho_from_addresses(_marker):
    try:
        return zoho("GET", "/settings/emails/actions/from_addresses").get("from_addresses", [])
    except Exception:
        return []


def zoho_upload_file(name, data):
    j = zoho("POST", "/files", files={"file": (name, data, "application/pdf")})
    return _check(j)["details"]["id"]


def zoho_send_mail(module, record_id, payload):
    return _check(zoho("POST", f"/{module}/{record_id}/actions/send_mail", json={"data": [payload]}))


def zoho_add_note(account_id, title, content):
    """Adds a note to the account, then reads the account's notes back to confirm it is really there."""
    made = _check(zoho("POST", f"/Accounts/{account_id}/Notes", json={"data": [{
        "Note_Title": title, "Note_Content": content,
        "Parent_Id": {"module": {"api_name": "Accounts"}, "id": str(account_id)}}]}))
    note_id = str((made.get("details") or {}).get("id") or "")
    if not note_id:
        raise ZohoError("Zoho accepted the note but did not return a note ID.")
    recent = zoho("GET", f"/Accounts/{account_id}/Notes",
                  params={"fields": "Note_Title,Created_Time", "per_page": 20, "sort_by": "Created_Time", "sort_order": "desc"})
    if note_id not in [str(n.get("id")) for n in recent.get("data", [])]:
        raise ZohoError(f"The note was created (ID {note_id}) but is not showing on the account.")
    return note_id


def zoho_attach(account_id, name, data):
    return _check(zoho("POST", f"/Accounts/{account_id}/Attachments", files={"file": (name, data, "application/pdf")}))


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
with st.sidebar:
    _side_logo = _img_tag(LOGO_DARK, 38)
    if _side_logo:
        render_html(f'<div style="margin-bottom:6px">{_side_logo}</div><div class="pe-brand"><div class="g">Onboarding Manager</div></div>')
    else:
        render_html(f'<div class="pe-brand"><div class="pe-logo">{ICON_PHONE}</div><div><div class="n">{esc(BRAND)}</div>'
                    '<div class="g">Onboarding Manager</div></div></div>')
    render_html('<div class="pe-row"><span><span class="pe-dot" style="background:var(--%s)"></span>Zoho CRM</span><b>%s</b></div>'
                % (("good", "Connected") if ZOHO_READY else ("warn", "Not set up")))
    st.write("")
    with st.expander("Zoho token helper", expanded=False):
        st.caption("Use this once to get the refresh token for Streamlit Secrets.")
        st.markdown("**1.** Open [api-console.zoho.eu](https://api-console.zoho.eu), choose your Self Client, "
                    "and on **Generate Code** paste this scope:")
        st.code(ZOHO_SCOPE, language=None)
        st.markdown("**2.** Paste the grant code below within its time limit.")
        cid = sec("ZOHO_CLIENT_ID") or st.text_input("Client ID", key="th_cid")
        csecret = sec("ZOHO_CLIENT_SECRET") or st.text_input("Client secret", type="password", key="th_cs")
        grant = st.text_input("Grant code", key="th_grant")
        if st.button("Get refresh token", **FULL_WIDTH):
            if not (cid and csecret and grant.strip()):
                st.error("Client ID, client secret and grant code are all needed.")
            else:
                try:
                    r = requests.post(f"{ZOHO_ACCOUNTS}/oauth/v2/token", timeout=30, data={
                        "grant_type": "authorization_code", "client_id": cid,
                        "client_secret": csecret, "code": grant.strip()})
                    j = r.json()
                    if j.get("refresh_token"):
                        st.success("Add this line to Streamlit Secrets:")
                        st.code(f'ZOHO_REFRESH_TOKEN = "{j["refresh_token"]}"', language="toml")
                    else:
                        st.error(f"Zoho said: {j.get('error', 'no refresh token returned')}. "
                                 "Grant codes expire quickly and only work once - generate a fresh one.")
                except Exception as e:
                    st.error(f"Could not reach Zoho: {e}")
    st.write("")
    if st.button("Log out", **FULL_WIDTH):
        st.session_state.clear()
        st.rerun()


# ----------------------------------------------------------------------------
# Input parsing
# ----------------------------------------------------------------------------
def clean_slug(s):
    return re.sub(r"[^a-z0-9-]", "", (s or "").strip().lower())


def join_url(slug, domain, path_or_url):
    p = (path_or_url or "").strip()
    if not p:
        return ""
    if p.lower().startswith("http"):
        return p
    return f"https://{slug}.{domain.strip().strip('/')}/{p.strip('/')}/".replace("//", "/").replace("https:/", "https://")


def parse_ranges(text):
    """'1000-1003, 5000' -> [(1000, 1003), (5000, 5000)] plus warnings."""
    out, warns = [], []
    for part in re.split(r"[,\n;]+", text or ""):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*(?:-|–|to)\s*(\d+)", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            out.append((min(a, b), max(a, b)))
        elif part.isdigit():
            out.append((int(part), int(part)))
        else:
            warns.append(f"Couldn't read \"{part}\" - use numbers or ranges like 1000-1020.")
    return out, warns


def describe_blocks(exts):
    """Summarises the runs of consecutive extensions, e.g. '1000-1003 (4), 2000-2010 (11)'."""
    nums = sorted({int(e) for e in exts})
    blocks, start, prev = [], None, None
    for n in nums:
        if start is None:
            start = prev = n
        elif n == prev + 1:
            prev = n
        else:
            blocks.append((start, prev)); start = prev = n
    if start is not None:
        blocks.append((start, prev))
    bits = [f"{a}-{b} ({b - a + 1})" if b > a else f"{a} (1)" for a, b in blocks]
    return ", ".join(bits[:30]) + (f" and {len(bits) - 30} more groups" if len(bits) > 30 else "")


def parse_extensions(ranges_text, named_text):
    """Returns (sorted list of (ext, name)), list of warnings."""
    found, warns = {}, []
    for part in re.split(r"[,\n;]+", ranges_text or ""):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)\s*(?:-|–|to)\s*(\d+)", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            if b < a:
                a, b = b, a
            if b - a + 1 > MAX_EXTENSIONS:
                warns.append(f"\"{part}\" is {b - a + 1:,} extensions - too many to list. "
                             "Enter the ranges actually in use, e.g. 1000-1020, 5000-5002.")
                continue
            width = len(m.group(1))
            for n in range(a, b + 1):
                found.setdefault(str(n).zfill(width), "")
        elif part.isdigit():
            found.setdefault(part, "")
        else:
            warns.append(f"Couldn't read \"{part}\" - use numbers or ranges like 1000-1020.")
    for line in (named_text or "").splitlines():
        m = re.match(r"\s*(\d+)\s*[,;:\t-]?\s*(.*)$", line)
        if m and m.group(1):
            found[m.group(1)] = m.group(2).strip()
        elif line.strip():
            warns.append(f"Couldn't read the named user line \"{line.strip()}\" - start it with the extension number.")
    if len(found) > MAX_EXTENSIONS:
        warns.append(f"Only the first {MAX_EXTENSIONS:,} extensions are used.")
    exts = sorted(found.items(), key=lambda kv: (len(kv[0]), kv[0]))[:MAX_EXTENSIONS]
    return exts, warns


EMAIL_RE = re.compile(r"[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+")


def parse_extension_csv(raw):
    """Reads ONLY extension number, name and email address from a phone-system export.
    Passwords and every other column are never kept."""
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
    try:
        reader = csv.DictReader(io.StringIO(text))
        cols = {re.sub(r"[^a-z]", "", (c or "").lower()): c for c in (reader.fieldnames or [])}
    except csv.Error:
        return [], "That file couldn't be read as a CSV."
    ext_col = next((cols[k] for k in ("extension", "extensionnumber", "ext", "number", "username") if k in cols), None)
    if not ext_col:
        return [], "Couldn't find an 'Extension' column in that file."
    first = cols.get("firstname")
    last = cols.get("lastname")
    full = next((cols[k] for k in ("name", "fullname", "displayname", "calleridname") if k in cols), None)
    mail = next((cols[k] for k in ("emailaddress", "email", "useremail") if k in cols), None)
    rows, seen = [], set()
    for r in reader:
        ext = (r.get(ext_col) or "").strip()
        if not ext.isdigit() or ext in seen:
            continue
        seen.add(ext)
        name = " ".join(p for p in ((r.get(first) or "").strip() if first else "",
                                    (r.get(last) or "").strip() if last else "") if p)
        if not name and full:
            name = (r.get(full) or "").strip()
        email = (r.get(mail) or "").strip() if mail else ""
        rows.append({"Include": True, "Extension": ext, "Name": name, "Email": email if EMAIL_RE.fullmatch(email) else ""})
        if len(rows) >= MAX_EXTENSIONS:
            break
    if not rows:
        return [], "No extension numbers were found in that file."
    return rows, ""


def fill_staff_template(body, name, ext, pw, address):
    first = (name or "").split(" ")[0] or "there"
    out = body
    for k, v in (("{first_name}", first), ("{name}", name or ""), ("{extension}", ext),
                 ("{password}", pw), ("{address}", address)):
        out = out.replace(k, v)
    return out


def lines(text):
    return [l.strip() for l in (text or "").splitlines() if l.strip()]


@st.cache_data(show_spinner=False, max_entries=20)
def build_documents(d, want_cards):
    out = {"manager": pdfs.build_manager_pack(d), "staff": pdfs.build_staff_guide(d)}
    if want_cards:
        out["cards"] = pdfs.build_login_cards(d)
    return out


@st.cache_data(show_spinner=False, max_entries=20)
def preview_png(pdf_bytes, page=0):
    try:
        import pymupdf
        doc = pymupdf.open(stream=pdf_bytes, filetype="pdf")
        return doc[page].get_pixmap(dpi=110).tobytes("png"), len(doc)
    except Exception:
        return None, 0


def file_stub(company):
    return re.sub(r"[^A-Za-z0-9]+", "-", company).strip("-") or "Customer"


# ----------------------------------------------------------------------------
# Page
# ----------------------------------------------------------------------------
hero = st.empty()
ss = st.session_state
ss.setdefault("zoho_account", None)
ss.setdefault("zoho_contacts", [])
ss.setdefault("zoho_results", [])


def use_account():
    acc = next((a for a in ss.zoho_results if a["id"] == ss.get("zoho_pick")), None)
    if not acc:
        return
    ss.zoho_account = acc
    ss.company = acc.get("Account_Name", "")
    try:
        ss.zoho_contacts = zoho_contacts(acc["id"])
    except Exception as e:
        ss.zoho_contacts = []
        ss.zoho_error = str(e)
    if ss.zoho_contacts:
        first = ss.zoho_contacts[0]
        ss.contact_name = first.get("Full_Name") or ""
        ss.contact_email = first.get("Email") or ""


def use_contact():
    c = next((c for c in ss.zoho_contacts if c["id"] == ss.get("zoho_contact_pick")), None)
    if c:
        ss.contact_name = c.get("Full_Name") or ""
        ss.contact_email = c.get("Email") or ""


left, right = st.columns([1.75, 1], gap="large")

with left:
    # ---- 01 Customer -----------------------------------------------------
    with st.container(key="card-customer"):
        section_header("01", "Customer", "Who the pack is for")
        if ZOHO_READY:
            c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
            q = c1.text_input("Find the account in Zoho", placeholder="Start typing the account name", key="zoho_q")
            if c2.button("Search", **FULL_WIDTH) and q.strip():
                try:
                    ss.zoho_results = zoho_search_accounts(q)
                    if not ss.zoho_results:
                        st.warning("No Zoho accounts start with that name.")
                except Exception as e:
                    st.error(f"Zoho search failed: {e}")
            if ss.zoho_results:
                c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
                c1.selectbox("Matching accounts", [a["id"] for a in ss.zoho_results], key="zoho_pick",
                             format_func=lambda i: next(
                                 (f"{a.get('Account_Name', '')}" + (f" - {a['Billing_City']}" if a.get("Billing_City") else "")
                                  for a in ss.zoho_results if a["id"] == i), i))
                c2.button("Use this account", on_click=use_account, type="primary", **FULL_WIDTH)
            if ss.get("zoho_error"):
                st.error(f"Couldn't load contacts: {ss.pop('zoho_error')}")
            if ss.zoho_account:
                render_html(f'<div style="margin:2px 0 12px">{chip("Linked to Zoho: " + ss.zoho_account.get("Account_Name", ""), "good")}</div>')
                if ss.zoho_contacts:
                    st.selectbox("Contact to send to", [c["id"] for c in ss.zoho_contacts], key="zoho_contact_pick",
                                 on_change=use_contact,
                                 format_func=lambda i: next((f"{c.get('Full_Name', '')} - {c.get('Email', '')}"
                                                             for c in ss.zoho_contacts if c["id"] == i), i))
                else:
                    st.warning("This account has no contacts with an email address. Add one in Zoho, then search again - "
                               "Zoho will only email addresses it holds on a record.")
        c1, c2 = st.columns(2)
        company = c1.text_input("Company name", key="company", placeholder="e.g. Currans").strip()
        slug = clean_slug(c2.text_input("Site name (web address prefix)", key="slug", placeholder="e.g. currans",
                                        help="The first part of their Call Scope address. It is also the start of every staff password."))
        c1, c2 = st.columns(2)
        contact_name = c1.text_input("Main contact name", key="contact_name").strip()
        contact_email = c2.text_input("Main contact email", key="contact_email").strip()

    # ---- 02 Portals ------------------------------------------------------
    with st.container(key="card-portals"):
        section_header("02", "Logins", "The addresses and passwords for this customer's site")
        domain = DEFAULT_DOMAIN
        show_slug = slug or "sitename"
        rec_url = join_url(show_slug, domain, RECORDINGS_PATH)
        ai_url = join_url(show_slug, domain, STAFF_PATH)

        st.markdown("**Call recordings** - admin only")
        render_html(f'<div class="pe-url">{esc(rec_url)}</div>')
        c1, c2 = st.columns(2)
        rec_user = c1.text_input("Admin username", value="Admin", key="rec_user").strip()
        rec_pass = c2.text_input("Admin password", key="rec_pass").strip()

        st.markdown("**Manager dashboard**")
        c1, c2, c3 = st.columns([2, 1, 1])
        mgr_in = c1.text_input("Dashboard address", value=DEFAULT_MANAGER_PATH, key="mgr_in",
                               placeholder="/dashboard/  or a full https:// address",
                               help="Type just the ending (e.g. /dashboard/) or paste the full address. Leave blank to leave the dashboard out of the pack.")
        mgr_user = c2.text_input("Username (if any)", key="mgr_user").strip()
        mgr_pass = c3.text_input("Password", key="mgr_pass").strip()
        mgr_url = join_url(show_slug, domain, mgr_in)
        if mgr_url:
            render_html(f'<div class="pe-url">{esc(mgr_url)}</div>')

        st.markdown("**Staff AI portal** - everyone")
        render_html(f'<div class="pe-url">{esc(ai_url)}</div>')
        st.caption(f"Each person logs in with their extension number. Their password is the site name followed by "
                   f"the extension - for example **{show_slug}1000**.")

    # ---- 03 Users --------------------------------------------------------
    with st.container(key="card-users"):
        section_header("03", "Staff extensions", "Used for the login list and the cut-out login cards")
        up = st.file_uploader("Upload the extensions export (CSV)", type=["csv"], key="ext_csv",
                              help="The extensions CSV downloaded from the phone system. Only the extension number, "
                                   "name and email address columns are read - passwords and everything else in the file are ignored.")
        csv_rows, csv_error = ([], "")
        if up is not None:
            csv_rows, csv_error = parse_extension_csv(up.getvalue())
            if csv_error:
                st.error(csv_error)
        picked = []
        if csv_rows:
            total_in_file = len(csv_rows)
            keep_text = st.text_input(
                "Only use these extension ranges (leave blank to use the whole file)", key="keep_ranges",
                placeholder="e.g. 1000-1003, 5000-5002",
                help="For shared (tenanted) phone systems, where the export also holds other customers' extensions. "
                     "Only extensions inside these ranges are used.")
            st.caption("In this file: " + describe_blocks([r["Extension"] for r in csv_rows]))
            keep, keep_warns = parse_ranges(keep_text)
            for w in keep_warns:
                st.warning(w)
            if keep:
                csv_rows = [r for r in csv_rows if any(a <= int(r["Extension"]) <= b for a, b in keep)]
                if not csv_rows:
                    st.warning("No extensions in the file fall inside those ranges.")
        if csv_rows:
            domains = sorted({r["Email"].split("@")[1].lower() for r in csv_rows if r.get("Email")})
            st.caption(f"Using {len(csv_rows)} of {total_in_file} extensions from {up.name}."
                       + (f" Email domains: {', '.join(domains[:8])}{' and more' if len(domains) > 8 else ''}." if domains else "")
                       + " Untick any that shouldn't get a login (spare lines, meeting rooms) and correct names if needed.")
            edited = st.data_editor(
                csv_rows, key=f"ext_editor_{abs(hash((up.getvalue(), keep_text)))}", hide_index=True, num_rows="fixed",
                height=min(38 + 35 * len(csv_rows), 420), **FULL_WIDTH,
                column_config={
                    "Include": st.column_config.CheckboxColumn("Include", width="small"),
                    "Extension": st.column_config.TextColumn("Extension", disabled=True, width="small"),
                    "Name": st.column_config.TextColumn("Name", width="medium"),
                    "Email": st.column_config.TextColumn("Email (for individual sends)", width="large"),
                })
            picked = [(str(r["Extension"]), ((r.get("Name") or "").strip(), (r.get("Email") or "").strip()))
                      for r in edited if r.get("Include")]
        with st.expander("Or type extensions in by hand", expanded=False):
            ranges_text = st.text_input("Extension numbers or ranges", key="ranges",
                                        placeholder="e.g. 1000-1012, 5000-5002")
            named_text = st.text_area("Names and emails (optional) - one per line, extension first", key="named", height=110,
                                      placeholder="1000, Sarah Jones, sarah@example.co.uk\n1001, Tom Blake")
        typed, ext_warns = parse_extensions(ranges_text, named_text)
        merged = dict(picked)
        for e, n in typed:
            m = EMAIL_RE.search(n)
            em = m.group(0) if m else ""
            n = n.replace(em, "").strip(" ,;<>-") if em else n
            if n or em or e not in merged:
                merged[e] = (n or merged.get(e, ("", ""))[0], em or merged.get(e, ("", ""))[1])
        ordered = sorted(merged.items(), key=lambda kv: (len(kv[0]), kv[0]))[:MAX_EXTENSIONS]
        ext_pairs = [(e, v[0]) for e, v in ordered]
        email_by_ext = {e: v[1] for e, v in ordered if EMAIL_RE.fullmatch(v[1] or "")}
        for w in ext_warns:
            st.warning(w)
        c1, c2 = st.columns(2)
        show_passwords = c1.toggle("Show passwords in the pack", value=True, key="w_showpw",
                                   help="Turn off to show 'Sent separately' instead, if you'd rather give passwords by phone.")
        want_cards = c2.toggle("Make cut-out login cards", value=True, key="w_cards",
                               disabled=not ext_pairs or len(ext_pairs) > CARD_LIMIT)
        if len(ext_pairs) > CARD_LIMIT:
            st.caption(f"Login cards are available for up to {CARD_LIMIT} extensions.")

        with st.expander("Edit the wording in the documents"):
            word = {}
            for key, label in (("rec", "Call recordings"), ("mgr", "Manager dashboard"), ("ai", "Staff AI portal")):
                st.markdown(f"**{label}**")
                c1, c2 = st.columns([1, 2])
                word[f"{key}_title"] = c1.text_input("Name", DEFAULT_WORDING[f"{key}_title"], key=f"w_{key}_title")
                word[f"{key}_desc"] = c2.text_input("One-line description", DEFAULT_WORDING[f"{key}_desc"], key=f"w_{key}_desc")
                word[f"{key}_bullets"] = st.text_area("What they'll find (one per line)", DEFAULT_WORDING[f"{key}_bullets"],
                                                      key=f"w_{key}_bullets", height=80)

# ---- validation -------------------------------------------------------------
missing = []
if not company:
    missing.append("Company name")
if not slug:
    missing.append("Site name")
if not rec_user or not rec_pass:
    missing.append("Admin username and password")
if mgr_url and not mgr_pass:
    missing.append("Manager dashboard password")
ready = not missing

docs = {}
if ready:
    exts = [(e, n, PW_PATTERN.replace("{slug}", slug).replace("{ext}", e)) for e, n in ext_pairs]
    logo = LOGO_DARK
    data = dict(
        brand=BRAND, company=company, slug=slug, contact_name=contact_name,
        date_str=dt.date.today().strftime("%-d %B %Y"),
        support_email=SUPPORT_EMAIL, support_phone=SUPPORT_PHONE, website=WEBSITE,
        logo_path=logo if os.path.exists(logo) else "",
        rec_url=rec_url, rec_user=rec_user, rec_pass=rec_pass,
        mgr_url=mgr_url, mgr_user=mgr_user, mgr_pass=mgr_pass,
        ai_url=ai_url, pw_pattern=PW_PATTERN, exts=exts, show_passwords=show_passwords,
        **{k: (lines(v) if k.endswith("_bullets") else v.strip()) for k, v in word.items()},
    )
    make_cards = bool(want_cards and exts and len(exts) <= CARD_LIMIT)
    try:
        docs = build_documents(data, make_cards)
    except Exception as e:
        st.error(f"The documents could not be built: {e}")
        ready = False

stub = file_stub(company)
FILES = {
    "manager": (f"{BRAND} Access Pack - {stub}.pdf", "Access Pack (main contact only)"),
    "staff": (f"{BRAND} Staff Guide - {stub}.pdf", "Staff Guide (safe to share)"),
    "cards": (f"{BRAND} Login Cards - {stub}.pdf", "Staff login cards"),
}

# ---- summary (right) --------------------------------------------------------
with right:
    with st.container(key="card-summary"):
        section_header("✓", "Pack summary", "Updates as you type")
        rows = [
            ("Customer", company or "-"),
            ("Site", f"{slug}.{DEFAULT_DOMAIN}" if slug else "-"),
            ("Main contact", contact_name or "-"),
            ("Logins included", "3 portals" if mgr_url else "2 portals"),
            ("Staff extensions", f"{len(ext_pairs):,}" if ext_pairs else "None listed"),
            ("With an email address", f"{len(email_by_ext):,}" if ext_pairs else "-"),
            ("Zoho account", ss.zoho_account.get("Account_Name", "") if ss.zoho_account else "Not linked"),
        ]
        render_html("".join(f'<div class="pe-row"><span>{esc(a)}</span><b>{esc(b)}</b></div>' for a, b in rows))
        st.write("")
        if not ready:
            render_html('<div style="display:flex;flex-wrap:wrap;gap:6px">'
                        + "".join(chip("Needed: " + m, "warn") for m in missing) + "</div>")
        else:
            notes = []
            if not mgr_url:
                notes.append(chip("Manager dashboard left out", "warn"))
            if not ext_pairs:
                notes.append(chip("No extension list", "warn"))
            if not show_passwords:
                notes.append(chip("Passwords hidden", "accent"))
            notes.append(chip("Documents ready", "good"))
            render_html('<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:14px">' + "".join(notes) + "</div>")
            for key in ("manager", "staff", "cards"):
                if key in docs:
                    st.download_button(f"Download {FILES[key][1]}", docs[key], file_name=FILES[key][0],
                                       mime="application/pdf", key=f"dl_{key}",
                                       type="primary" if key == "manager" else "secondary", **FULL_WIDTH)
            if ext_pairs:
                buf = io.StringIO()
                wr = csv.writer(buf)
                wr.writerow(["Extension / username", "Name", "Password", "Web address"])
                for e, n, p in exts:
                    wr.writerow([e, n, p, ai_url])
                st.download_button("Download login list (CSV)", buf.getvalue(), file_name=f"{stub}-staff-logins.csv",
                                   mime="text/csv", key="dl_csv", **FULL_WIDTH)

# ---- 04 Preview -------------------------------------------------------------
with st.container(key="card-docs"):
    section_header("04", "Preview", "Check the documents before they go out")
    if not ready:
        render_html(f'<div class="pe-empty"><div class="ic">{ICON_PHONE}</div><div class="t">Nothing to preview yet</div>'
                    '<ol><li>Enter the company and site name</li><li>Add the admin password</li>'
                    '<li>List the staff extensions</li></ol></div>')
    else:
        tabs = st.tabs([FILES[k][1] for k in docs])
        for tab, key in zip(tabs, docs):
            with tab:
                png, n_pages = preview_png(docs[key], 0)
                if png:
                    cols = st.columns(2)
                    cols[0].image(png, caption=f"Page 1 of {n_pages}")
                    if n_pages > 1:
                        png2, _ = preview_png(docs[key], 1)
                        cols[1].image(png2, caption=f"Page 2 of {n_pages}")
                else:
                    st.caption("Preview unavailable - use the download button to open the PDF.")

# ---- 05 Send & log ----------------------------------------------------------
sent = ss.get("sent_for") == (company, contact_email)
with st.container(key="card-send"):
    section_header("05", "Send from Zoho", "Email the main contact, each member of staff, or both - all logged on the account")
    if not ZOHO_READY:
        render_html(f'<div class="pe-empty"><div class="ic">{ICON_PHONE}</div><div class="t">Zoho isn\'t connected yet</div>'
                    '<ol><li>Add ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET to Secrets</li>'
                    '<li>Use the token helper in the sidebar</li><li>Add ZOHO_REFRESH_TOKEN to Secrets</li></ol>'
                    '<div style="margin-top:10px;font-size:.84rem">Until then, download the PDFs and send them yourself.</div></div>')
    elif not ready:
        st.caption("Complete the details above first.")
    elif not ss.zoho_account:
        st.caption("Search for the customer in section 01 and press **Use this account** so the email can be logged against it.")
    else:
        tab_main, tab_staff = st.tabs(["Main contact", "Individual staff"])
        with tab_main:
            contact = next((c for c in ss.zoho_contacts if (c.get("Email") or "").lower() == contact_email.lower()), None)
            froms = zoho_from_addresses(sec("ZOHO_REFRESH_TOKEN")[-6:])
            c1, c2 = st.columns(2)
            if froms:
                idx = c1.selectbox("Send from", range(len(froms)),
                                   format_func=lambda i: f"{froms[i].get('email')} ({froms[i].get('user_name', '')})")
                sender = froms[idx]
            else:
                manual = c1.text_input("Send from (must be an address set up in Zoho CRM)", key="from_manual")
                sender = {"email": manual.strip(), "user_name": BRAND, "type": ""}
            c2.text_input("Send to", value=f"{contact_name} <{contact_email}>" if contact_email else "", disabled=True)
            if not contact:
                st.warning("The main contact's email doesn't match a contact on this Zoho account. Pick a contact in "
                           "section 01 - Zoho only sends to addresses held on a record.")

            first = contact_name.split(" ")[0] if contact_name else "there"
            attach_keys = st.multiselect("Attach", list(docs), default=[k for k in ("manager", "staff") if k in docs],
                                         format_func=lambda k: FILES[k][1])
            default_body = (
                f"Hi {first},\n\n"
                f"Great news - your {BRAND} service for {company} is now live.\n\n"
                f"Attached is everything you need to get started:\n\n"
                + ("- Access Pack - your own copy, with the administrator"
                   + (" and manager dashboard" if mgr_url else "") + " logins. Please keep this one to yourself.\n"
                   if "manager" in attach_keys else "")
                + ("- Staff Guide - a one-page guide you can forward to your whole team. It only covers their own personal login.\n"
                   if "staff" in attach_keys else "")
                + ("- Login Cards - a printable card for each member of staff.\n" if "cards" in attach_keys else "")
                + f"\nIf you have any questions at all, just reply to this email.\n\nKind regards\n{EMAIL_SIGN_OFF}"
            )
            sig = str(abs(hash((company, first, tuple(attach_keys), bool(mgr_url)))))
            subject = st.text_input("Subject", value=f"Welcome to {BRAND} - your login details for {company}", key=f"subj_{sig}")
            body = st.text_area("Message", value=default_body, height=280, key=f"body_{sig}")
            c1, c2 = st.columns(2)
            add_note = c1.toggle("Add a note to the account", value=True, key="w_note")
            file_docs = c2.toggle("Save the PDFs on the account", value=True, key="w_file",
                                  help="Stores the attached PDFs under Attachments on the Zoho account. "
                                       "Turn off if you don't want passwords held in the CRM.")

            can_send = bool(contact and sender.get("email") and attach_keys and subject.strip())
            if sent:
                st.success(f"Sent to {contact_email} and logged on {ss.zoho_account.get('Account_Name', '')}.")
                for line in ss.get("sent_log", []):
                    st.caption(line)
            if st.button("Send again" if sent else "Send and log in Zoho", type="primary", disabled=not can_send):
                log = []
                try:
                    with st.status("Sending through Zoho...", expanded=True) as status:
                        st.write("Uploading the PDFs")
                        ids = [{"id": zoho_upload_file(FILES[k][0], docs[k])} for k in attach_keys]
                        st.write("Sending the email")
                        paras = "".join(
                            f'<p style="margin:0 0 12px">{esc(p).replace(chr(10), "<br>")}</p>' for p in body.strip().split("\n\n"))
                        payload = {
                            "from": {"user_name": sender.get("user_name") or BRAND, "email": sender["email"]},
                            "to": [{"user_name": contact_name or contact_email, "email": contact_email}],
                            "subject": subject.strip(),
                            "content": f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#1B2333;line-height:1.5">{paras}</div>',
                            "mail_format": "html",
                            "attachments": ids,
                        }
                        if sender.get("type") == "org_email":
                            payload["org_email"] = True
                        zoho_send_mail("Contacts", contact["id"], payload)
                        log.append(f"Email sent from {sender['email']} with {len(ids)} attachment(s).")
                        acc_id = ss.zoho_account["id"]
                        st.write("Adding the note to the account")
                        try:
                            note_id = zoho_add_note(
                                acc_id, NOTE_TITLE,
                                f"{BRAND} onboarding sent to {contact_name} ({contact_email}) on "
                                f"{dt.datetime.now().strftime('%d/%m/%Y %H:%M')} from {sender['email']}.\n"
                                f"Site: https://{slug}.{DEFAULT_DOMAIN}/\n"
                                f"Documents: {', '.join(FILES[k][1] for k in attach_keys)}\n"
                                f"Staff extensions listed: {len(ext_pairs)}")
                            log.append(f"Note \"{NOTE_TITLE}\" added to the account and confirmed (note ID {note_id}).")
                        except Exception as note_err:
                            log.append(f"NOTE NOT ADDED - Zoho said: {note_err}")
                        if file_docs:
                            st.write("Saving the PDFs on the account")
                            for k in attach_keys:
                                zoho_attach(acc_id, FILES[k][0], docs[k])
                            log.append("PDFs saved under the account's attachments.")
                        status.update(label="Sent and logged", state="complete", expanded=False)
                    ss.sent_for = (company, contact_email)
                    ss.sent_log = log
                    st.rerun()
                except Exception as e:
                    for line in log:
                        st.caption("Done: " + line)
                    st.error(f"Zoho stopped at this step: {e}")

        with tab_staff:
            with_email = [(e, n, p) for e, n, p in exts if e in email_by_ext]
            if not with_email:
                st.caption("No staff email addresses yet. Upload the extensions CSV in section 03 (it includes each "
                           "person's email) or add them in the table there.")
            else:
                st.caption(f"Sends each person their own login and a personal one-page guide. {len(with_email)} of "
                           f"{len(exts)} extensions have an email address. Each email is logged on the "
                           f"{ss.zoho_account.get('Account_Name', '')} account.")
                sfroms = zoho_from_addresses(sec("ZOHO_REFRESH_TOKEN")[-6:])
                if sfroms:
                    sidx = st.selectbox("Send from", range(len(sfroms)), key="staff_from",
                                        format_func=lambda i: f"{sfroms[i].get('email')} ({sfroms[i].get('user_name', '')})")
                    ssender = sfroms[sidx]
                else:
                    smanual = st.text_input("Send from (must be an address set up in Zoho CRM)", key="staff_from_manual")
                    ssender = {"email": smanual.strip(), "user_name": BRAND, "type": ""}
                done = ss.setdefault("staff_sent", {})
                label = {e: f"{e} - {n or 'No name'} - {email_by_ext[e]}" + ("  (sent)" if (slug, e) in done else "")
                         for e, n, p in with_email}
                chosen = st.multiselect("Send to", [e for e, _, _ in with_email],
                                        default=[e for e, _, _ in with_email if (slug, e) not in done],
                                        format_func=lambda e: label.get(e, e), key=f"staff_pick_{slug}_{len(with_email)}")
                s_subject = st.text_input("Subject", value=f"Your {BRAND} login", key="staff_subject")
                s_body = st.text_area(
                    "Message - the words in {brackets} are filled in for each person", height=260, key="staff_body",
                    value=("Hi {first_name},\n\n"
                           f"{company} now uses {BRAND}, and your personal login is ready.\n\n"
                           "Web address: {address}\nUsername: {extension}\nPassword: {password}\n\n"
                           "Your one-page guide is attached. If you have any trouble logging in, speak to your manager first.\n\n"
                           f"Kind regards\n{EMAIL_SIGN_OFF}"))
                c1, c2 = st.columns(2)
                s_attach = c1.toggle("Attach their personal guide (PDF)", value=True, key="w_staff_attach")
                s_note = c2.toggle("Add a note to the account", value=True, key="w_staff_note")
                if chosen:
                    e0 = chosen[0]
                    n0 = dict((e, n) for e, n, _ in exts).get(e0, "")
                    with st.expander(f"Preview the email for {n0 or e0}"):
                        st.text(fill_staff_template(s_body, n0, e0, PW_PATTERN.replace("{slug}", slug).replace("{ext}", e0), ai_url))
                if st.button(f"Send {len(chosen)} individual email{'s' if len(chosen) != 1 else ''}", type="primary",
                             disabled=not (chosen and ssender.get("email") and s_subject.strip()), key="staff_send"):
                    acc_id = ss.zoho_account["id"]
                    ok, failed = [], []
                    bar = st.progress(0.0, text="Sending...")
                    lookup = {e: (n, p) for e, n, p in exts}
                    for i, e in enumerate(chosen):
                        n, p = lookup[e]
                        to = email_by_ext[e]
                        bar.progress(i / len(chosen), text=f"Sending to {n or e} ({i + 1} of {len(chosen)})")
                        try:
                            text = fill_staff_template(s_body, n, e, p, ai_url)
                            paras = "".join(f'<p style="margin:0 0 12px">{esc(x).replace(chr(10), "<br>")}</p>'
                                            for x in text.strip().split("\n\n"))
                            payload = {
                                "from": {"user_name": ssender.get("user_name") or BRAND, "email": ssender["email"]},
                                "to": [{"user_name": n or to, "email": to}],
                                "subject": s_subject.strip(),
                                "content": f'<div style="font-family:Arial,Helvetica,sans-serif;font-size:14px;color:#1B2333;line-height:1.5">{paras}</div>',
                                "mail_format": "html",
                            }
                            if s_attach:
                                pdf = pdfs.build_staff_guide(data, person=(e, n, p))
                                payload["attachments"] = [{"id": zoho_upload_file(f"{BRAND} login - {file_stub(n or e)}.pdf", pdf)}]
                            if ssender.get("type") == "org_email":
                                payload["org_email"] = True
                            zoho_send_mail("Accounts", acc_id, payload)
                            ok.append((e, n, to))
                            done[(slug, e)] = True
                        except Exception as err:
                            failed.append((e, n, to, str(err)))
                    bar.progress(1.0, text="Finished")
                    if ok and s_note:
                        try:
                            zoho_add_note(acc_id, f"{BRAND} staff logins sent",
                                          f"Individual {BRAND} login emails sent on {dt.datetime.now().strftime('%d/%m/%Y %H:%M')} "
                                          f"from {ssender['email']} to {len(ok)} staff:\n"
                                          + "\n".join(f"{e} - {n or 'No name'} - {to}" for e, n, to in ok))
                        except Exception as err:
                            st.warning(f"Emails went, but the note could not be added: {err}")
                    ss.staff_result = (ok, failed)
                res = ss.get("staff_result")
                if res:
                    ok, failed = res
                    if ok:
                        st.success(f"{len(ok)} individual email{'s' if len(ok) != 1 else ''} sent and logged.")
                    for e, n, to, err in failed:
                        st.error(f"{e} {n} ({to}) was not sent - Zoho said: {err}")
                    if failed:
                        st.caption("If Zoho refuses an address, add that person as a contact on the account in Zoho and send again.")


# ---- hero (filled last so the stepper reflects this run) ---------------------
steps = [("Customer", bool(company and slug)), ("Logins", bool(rec_pass and (not mgr_url or mgr_pass))),
         ("Documents", ready), ("Sent", (sent or bool(ss.get("staff_result") and ss.staff_result[0])) and ready)]
active = next((i for i, (_, done) in enumerate(steps) if not done), len(steps))
parts = []
for i, (label, done) in enumerate(steps):
    cls = "done" if done else ("active" if i == active else "")
    parts.append(f'<div class="pe-step {cls}"><div class="num">{"✓" if done else i + 1}</div>{label}</div>')
render_html(
    '<div class="pe-hero"><div>'
    f'<div class="pe-eyebrow"><span class="dot"></span>{esc(BRAND)} · Customer onboarding</div>'
    '<div class="pe-title">Welcome packs, <span>ready to send</span></div>'
    '<div class="pe-sub">Enter a new site\'s details to create the customer\'s Access Pack and a Staff Guide they can share, '
    'then send and log it through Zoho.</div></div>'
    f'<div class="pe-stepper">{"<div class=pe-step-sep></div>".join(parts)}</div></div>', hero)
