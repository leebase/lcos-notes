// Rig self-test client: a gtkmm window that retitles itself with each typed key.
#include <gtkmm.h>
int main(int argc, char** argv)
{
  auto app = Gtk::Application::create(argc, argv, "com.leebase.LcosNotesRigSelftest");
  Gtk::Window w;
  w.set_title("rig ready");
  w.set_default_size(320, 200);
  w.signal_key_press_event().connect([&w](GdkEventKey* ev) {
    w.set_title(std::string("typed ") + gdk_keyval_name(ev->keyval));
    return true;
  }, false);
  w.show_all();
  return app->run(w);
}
