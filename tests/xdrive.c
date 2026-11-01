/* xdrive: minimal X11/XTest driver for the GUI acceptance tests.
 *
 *   xdrive windows PID       one line per top-level client window of PID:
 *                            "<id>\t<frame>\t<csd>\t<title>"  frame = 1 if the WM set
 *                            _NET_FRAME_EXTENTS, csd = 1 if the client set
 *                            _GTK_FRAME_EXTENTS (client-side decorations)
 *   xdrive activate ID       ask the WM to activate and focus the window
 *   xdrive close ID          ask the WM to close the window (_NET_CLOSE_WINDOW)
 *   xdrive key COMBO...      e.g. ctrl+s alt+Return Escape Down ctrl+Home
 *   xdrive type TEXT         type printable ASCII text
 *   xdrive geometry ID       "<x> <y> <w> <h> <fx> <fy> <fw> <fh>": the client area in root
 *                            coordinates, then the outer frame (client plus _NET_FRAME_EXTENTS)
 *   xdrive shot ID           binary PPM (P6) of the on-screen part of the client area, read
 *                            from the root window
 *   xdrive click ID X Y [MODS]  left click at client coordinates; MODS like shift or ctrl+shift
 *
 * SPDX-License-Identifier: Apache-2.0
 */
#include <X11/Xatom.h>
#include <X11/Xlib.h>
#include <X11/XKBlib.h>
#include <X11/Xutil.h>
#include <X11/extensions/XTest.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static Display *dpy;

static int get_cardinal(Window w, const char *name, unsigned long *out)
{
  Atom type; int fmt; unsigned long n, after; unsigned char *data = NULL;
  Atom a = XInternAtom(dpy, name, False);
  if (XGetWindowProperty(dpy, w, a, 0, 1, False, XA_CARDINAL, &type, &fmt, &n, &after, &data) != Success
      || !data || n < 1) {
    if (data) XFree(data);
    return 0;
  }
  *out = *(unsigned long *)data;
  XFree(data);
  return 1;
}

static int has_prop(Window w, const char *name)
{
  Atom type; int fmt; unsigned long n, after; unsigned char *data = NULL;
  Atom a = XInternAtom(dpy, name, False);
  int ok = XGetWindowProperty(dpy, w, a, 0, 4, False, AnyPropertyType, &type, &fmt, &n, &after, &data) == Success
           && type != None;
  if (data) XFree(data);
  return ok;
}

static void print_title(Window w)
{
  Atom type; int fmt; unsigned long n, after; unsigned char *data = NULL;
  Atom name = XInternAtom(dpy, "_NET_WM_NAME", False);
  Atom utf8 = XInternAtom(dpy, "UTF8_STRING", False);
  if (XGetWindowProperty(dpy, w, name, 0, 4096, False, utf8, &type, &fmt, &n, &after, &data) == Success && data) {
    fwrite(data, 1, n, stdout);
    XFree(data);
  }
}

static void walk(Window w, unsigned long pid)
{
  Window root, parent, *kids = NULL; unsigned int nk = 0;
  unsigned long p;
  if (get_cardinal(w, "_NET_WM_PID", &p) && p == pid && has_prop(w, "WM_STATE")) {
    XWindowAttributes at;
    if (XGetWindowAttributes(dpy, w, &at) && at.map_state == IsViewable) {
      printf("%lu\t%d\t%d\t", (unsigned long)w, has_prop(w, "_NET_FRAME_EXTENTS"), has_prop(w, "_GTK_FRAME_EXTENTS"));
      print_title(w);
      printf("\n");
    }
  }
  if (XQueryTree(dpy, w, &root, &parent, &kids, &nk)) {
    for (unsigned int i = 0; i < nk; i++) walk(kids[i], pid);
    if (kids) XFree(kids);
  }
}

static void client_message(Window w, const char *type, long l0, long l1)
{
  XEvent ev;
  memset(&ev, 0, sizeof ev);
  ev.xclient.type = ClientMessage;
  ev.xclient.window = w;
  ev.xclient.message_type = XInternAtom(dpy, type, False);
  ev.xclient.format = 32;
  ev.xclient.data.l[0] = l0;
  ev.xclient.data.l[1] = l1;
  XSendEvent(dpy, DefaultRootWindow(dpy), False, SubstructureRedirectMask | SubstructureNotifyMask, &ev);
  XFlush(dpy);
}

static void press(KeyCode kc, int down)
{
  XTestFakeKeyEvent(dpy, kc, down, CurrentTime);
  XFlush(dpy);
  usleep(15000);
}

static int send_keysym(KeySym ks, unsigned int mods)
{
  KeyCode kc = XKeysymToKeycode(dpy, ks);
  if (!kc) return 0;
  int need_shift = 0;
  if (XkbKeycodeToKeysym(dpy, kc, 0, 0) != ks && XkbKeycodeToKeysym(dpy, kc, 0, 1) == ks) need_shift = 1;
  KeyCode ctrl = XKeysymToKeycode(dpy, XK_Control_L), alt = XKeysymToKeycode(dpy, XK_Alt_L),
          shift = XKeysymToKeycode(dpy, XK_Shift_L);
  if (mods & ControlMask) press(ctrl, 1);
  if (mods & Mod1Mask) press(alt, 1);
  if ((mods & ShiftMask) || need_shift) press(shift, 1);
  press(kc, 1);
  press(kc, 0);
  if ((mods & ShiftMask) || need_shift) press(shift, 0);
  if (mods & Mod1Mask) press(alt, 0);
  if (mods & ControlMask) press(ctrl, 0);
  return 1;
}

static int combo(const char *spec)
{
  char buf[256];
  snprintf(buf, sizeof buf, "%s", spec);
  unsigned int mods = 0;
  char *tok = strtok(buf, "+"), *last = NULL;
  while (tok) {
    if (last) {
      if (!strcasecmp(last, "ctrl")) mods |= ControlMask;
      else if (!strcasecmp(last, "alt")) mods |= Mod1Mask;
      else if (!strcasecmp(last, "shift")) mods |= ShiftMask;
      else return 0;
    }
    last = tok;
    tok = strtok(NULL, "+");
  }
  if (!last) return 0;
  KeySym ks = XStringToKeysym(last);
  if (ks == NoSymbol) return 0;
  return send_keysym(ks, mods);
}

static void client_box(Window w, int *x, int *y, unsigned int *cw, unsigned int *ch)
{
  Window root, child; int gx, gy; unsigned int bw, depth;
  XGetGeometry(dpy, w, &root, &gx, &gy, cw, ch, &bw, &depth);
  XTranslateCoordinates(dpy, w, root, 0, 0, x, y, &child);
}

static void frame_extents(Window w, long ext[4])
{
  Atom type; int fmt; unsigned long n, after; unsigned char *data = NULL;
  ext[0] = ext[1] = ext[2] = ext[3] = 0;
  Atom a = XInternAtom(dpy, "_NET_FRAME_EXTENTS", False);
  if (XGetWindowProperty(dpy, w, a, 0, 4, False, XA_CARDINAL, &type, &fmt, &n, &after, &data) == Success
      && data && n == 4)
    for (int i = 0; i < 4; i++) ext[i] = ((long *)data)[i];
  if (data) XFree(data);
}

static unsigned int modmask(const char *spec)
{
  char buf[64]; unsigned int mods = 0;
  snprintf(buf, sizeof buf, "%s", spec);
  for (char *tok = strtok(buf, "+"); tok; tok = strtok(NULL, "+")) {
    if (!strcasecmp(tok, "ctrl")) mods |= ControlMask;
    else if (!strcasecmp(tok, "alt")) mods |= Mod1Mask;
    else if (!strcasecmp(tok, "shift")) mods |= ShiftMask;
    else return (unsigned int)-1;
  }
  return mods;
}

int main(int argc, char **argv)
{
  if (argc < 3) { fprintf(stderr, "usage: xdrive windows|activate|close|key|type|geometry|shot|click ARG...\n"); return 2; }
  dpy = XOpenDisplay(NULL);
  if (!dpy) { fprintf(stderr, "xdrive: cannot open display\n"); return 3; }
  const char *cmd = argv[1];
  if (!strcmp(cmd, "windows")) {
    walk(DefaultRootWindow(dpy), strtoul(argv[2], NULL, 10));
  } else if (!strcmp(cmd, "activate")) {
    Window w = (Window)strtoul(argv[2], NULL, 10);
    client_message(w, "_NET_ACTIVE_WINDOW", 2, CurrentTime);
    XSetInputFocus(dpy, w, RevertToParent, CurrentTime);
    XSync(dpy, False);
  } else if (!strcmp(cmd, "close")) {
    client_message((Window)strtoul(argv[2], NULL, 10), "_NET_CLOSE_WINDOW", CurrentTime, 2);
  } else if (!strcmp(cmd, "key")) {
    for (int i = 2; i < argc; i++)
      if (!combo(argv[i])) { fprintf(stderr, "xdrive: bad key %s\n", argv[i]); return 2; }
  } else if (!strcmp(cmd, "type")) {
    for (const char *p = argv[2]; *p; p++) {
      KeySym ks = (*p == ' ') ? XK_space : (KeySym)(unsigned char)*p;
      if (!send_keysym(ks, 0)) { fprintf(stderr, "xdrive: cannot type %c\n", *p); return 2; }
    }
  } else if (!strcmp(cmd, "geometry")) {
    Window w = (Window)strtoul(argv[2], NULL, 10);
    int x, y; unsigned int cw, ch; long e[4];
    client_box(w, &x, &y, &cw, &ch);
    frame_extents(w, e);  /* left, right, top, bottom */
    printf("%d %d %u %u %ld %ld %ld %ld\n", x, y, cw, ch, x - e[0], y - e[2], cw + e[0] + e[1], ch + e[2] + e[3]);
  } else if (!strcmp(cmd, "shot")) {
    Window w = (Window)strtoul(argv[2], NULL, 10);
    int x, y; unsigned int cw, ch;
    client_box(w, &x, &y, &cw, &ch);
    /* Only the part of the client area that is on screen can be read. */
    int sw = DisplayWidth(dpy, DefaultScreen(dpy)), sh = DisplayHeight(dpy, DefaultScreen(dpy));
    if (x < 0 || y < 0) { fprintf(stderr, "xdrive: window starts off screen\n"); return 2; }
    if (x + (int)cw > sw) cw = sw - x;
    if (y + (int)ch > sh) ch = sh - y;
    XImage *img = XGetImage(dpy, DefaultRootWindow(dpy), x, y, cw, ch, AllPlanes, ZPixmap);
    if (!img) { fprintf(stderr, "xdrive: cannot read image\n"); return 2; }
    printf("P6\n%u %u\n255\n", cw, ch);
    for (unsigned int j = 0; j < ch; j++)
      for (unsigned int i = 0; i < cw; i++) {
        unsigned long px = XGetPixel(img, i, j);
        unsigned char rgb[3] = {(px >> 16) & 255, (px >> 8) & 255, px & 255};
        fwrite(rgb, 1, 3, stdout);
      }
    XDestroyImage(img);
  } else if (!strcmp(cmd, "click")) {
    if (argc < 5) { fprintf(stderr, "xdrive: click ID X Y [MODS]\n"); return 2; }
    Window w = (Window)strtoul(argv[2], NULL, 10);
    int x, y; unsigned int cw, ch;
    client_box(w, &x, &y, &cw, &ch);
    unsigned int mods = argc > 5 ? modmask(argv[5]) : 0;
    if (mods == (unsigned int)-1) { fprintf(stderr, "xdrive: bad modifiers %s\n", argv[5]); return 2; }
    KeyCode ctrl = XKeysymToKeycode(dpy, XK_Control_L), alt = XKeysymToKeycode(dpy, XK_Alt_L),
            shift = XKeysymToKeycode(dpy, XK_Shift_L);
    XTestFakeMotionEvent(dpy, -1, x + atoi(argv[3]), y + atoi(argv[4]), CurrentTime);
    XFlush(dpy); usleep(60000);
    if (mods & ControlMask) press(ctrl, 1);
    if (mods & Mod1Mask) press(alt, 1);
    if (mods & ShiftMask) press(shift, 1);
    XTestFakeButtonEvent(dpy, 1, True, CurrentTime); XFlush(dpy); usleep(40000);
    XTestFakeButtonEvent(dpy, 1, False, CurrentTime); XFlush(dpy); usleep(40000);
    if (mods & ShiftMask) press(shift, 0);
    if (mods & Mod1Mask) press(alt, 0);
    if (mods & ControlMask) press(ctrl, 0);
  } else {
    fprintf(stderr, "xdrive: unknown command %s\n", cmd);
    return 2;
  }
  XSync(dpy, False);
  XCloseDisplay(dpy);
  return 0;
}
