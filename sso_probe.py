"""Diagnostic: what does ServiceNow's SSO page actually render to our browser?

Not part of the app flow. Run inside the pod to distinguish bot-detection from a
rendering/timing problem. Prints only page metadata - never credentials.
"""
import time, sys
import firefox_utils

SIGNON = ("https://signon.servicenow.com/x_snc_sso_auth.do?pageId=login"
          "&RelayState=%252Fapp%252Fservicenow_ud%252Fexks6phcbx6R8qjln0x7%252Fsso%252Fsaml"
          "%253FRelayState%253Dhttps%25253A%25252F%25252Fdeveloper.servicenow.com%25252Fnavpage.do"
          "&redirectUri=&email=")

def main():
    print("== starting driver ==", flush=True)
    d = firefox_utils.setup_firefox_driver()
    try:
        print("webdriver flag:", d.execute_script("return navigator.webdriver"), flush=True)
        print("userAgent:", d.execute_script("return navigator.userAgent")[:110], flush=True)
        d.set_page_load_timeout(45)
        t = time.time()
        try:
            d.get(SIGNON)
            print("get() returned in %.1fs" % (time.time() - t), flush=True)
        except Exception as e:
            print("get() %s after %.1fs" % (type(e).__name__, time.time() - t), flush=True)
        for i in range(1, 9):
            time.sleep(6)
            try:
                url = d.current_url
                nodes = d.execute_script("return document.querySelectorAll('*').length")
                ifr = len(d.find_elements("tag name", "iframe"))
                has_u = len(d.find_elements("css selector", "#username, #email"))
                inputs = len(d.find_elements("tag name", "input"))
                print(f"[t+{i*6:>2}s] nodes={nodes} inputs={inputs} iframes={ifr} user_field={has_u} url={url[:70]}", flush=True)
                if has_u:
                    print("USERNAME FIELD APPEARED", flush=True); break
            except Exception as e:
                print(f"[t+{i*6}s] inspect {type(e).__name__}", flush=True)
        # What is actually on top of the submit button? (click-interception cause)
        try:
            overlay = d.execute_script("""
              const out = {};
              const btn = document.querySelector('#identify-submit, #username_submit_button');
              if (btn) {
                const r = btn.getBoundingClientRect();
                out.btn = {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height),
                           visible: r.width>0 && r.height>0};
                const el = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
                out.topElement = el ? (el.tagName + '#' + (el.id||'') + '.' + (String(el.className)||'').slice(0,60)) : null;
                out.isButton = el === btn || (el && btn.contains(el));
              } else { out.btn = null; }
              const sus = [];
              document.querySelectorAll('body *').forEach(e => {
                const cs = getComputedStyle(e);
                const z = parseInt(cs.zIndex||'0');
                if ((cs.position==='fixed'||cs.position==='sticky') && z > 0 && e.offsetHeight > 30) {
                  sus.push(e.tagName + '#' + (e.id||'') + '.' + String(e.className||'').slice(0,40) + ' z=' + z);
                }
              });
              out.overlays = sus.slice(0, 8);
              out.consent = Array.from(document.querySelectorAll(
                '[id*=cookie i],[class*=cookie i],[id*=consent i],[class*=consent i],[id*=onetrust i],[class*=onetrust i],[id*=truste i]'
              )).slice(0,6).map(e => e.tagName + '#' + (e.id||'') + '.' + String(e.className||'').slice(0,40));
              return out;
            """)
            print("OVERLAY:", overlay, flush=True)
        except Exception as e:
            print("overlay probe:", type(e).__name__, flush=True)
        try:
            body = d.execute_script("return document.body ? document.body.innerText : ''")
            print("BODY TEXT:", " ".join(body.split())[:400], flush=True)
            print("TITLE:", (d.title or "")[:80], flush=True)
            for n, fr in enumerate(d.find_elements("tag name", "iframe")[:3]):
                d.switch_to.frame(fr)
                inner = d.execute_script("return document.body ? document.body.innerText : ''")
                fu = len(d.find_elements("css selector", "#username, #email"))
                print(f"IFRAME[{n}] user_field={fu} text={' '.join(inner.split())[:200]}", flush=True)
                d.switch_to.default_content()
        except Exception as e:
            print("body/iframe inspect:", type(e).__name__, flush=True)
    finally:
        try: d.quit()
        except Exception: pass
    print("== done ==", flush=True)

if __name__ == "__main__":
    main()
