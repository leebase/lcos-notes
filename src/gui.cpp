// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Lee Harrington
#include "core.hpp"
#include <gtkmm.h>
#include <gtksourceviewmm.h>
#include <fstream>
#include <iostream>
#include <map>
using namespace notes;
class Window : public Gtk::Window {
    Vault vault;
    Document document;
    Gtk::Box layout{Gtk::ORIENTATION_VERTICAL};
    Gtk::MenuBar menubar;
    Gtk::Paned panes{Gtk::ORIENTATION_HORIZONTAL};
    Gtk::ScrolledWindow tree_scroll, editor_scroll, tags_scroll, backlinks_scroll;
    Gtk::Notebook sidebar;
    Gtk::Stack views;
    Gtk::ScrolledWindow reading_scroll;
    Gtk::TextView reading_view;
    Glib::RefPtr<Gtk::TextBuffer> reading_buffer=Gtk::TextBuffer::create();
    std::map<std::string,Glib::RefPtr<Gtk::TextTag>> reading_tags;
    Render rendered;
    bool reading=false;
    bool reading_scroll_pending=false;
    bool initial_geometry_pending=true;
    Gtk::Paned content{Gtk::ORIENTATION_HORIZONTAL};
    Gtk::TreeView tags_tree, backlinks_tree;
    sigc::connection styling, reading_scrolling;
    Glib::RefPtr<Gtk::TextTag> resolved_tag, unresolved_tag;
    Gtk::TreeView tree;
    Gsv::View editor;
    Glib::RefPtr<Gsv::Buffer> buffer=Gsv::Buffer::create();
    Gtk::Statusbar status;
    struct Columns : Gtk::TreeModel::ColumnRecord {
        Gtk::TreeModelColumn<Glib::ustring> label,path,text;
        Gtk::TreeModelColumn<int> line,col;
        Columns(){add(label);add(path);add(text);add(line);add(col);}
    } columns;
    Glib::RefPtr<Gtk::TreeStore> store=Gtk::TreeStore::create(columns);
    Glib::RefPtr<Gtk::TreeStore> tag_store=Gtk::TreeStore::create(columns);
    Glib::RefPtr<Gtk::ListStore> backlink_store=Gtk::ListStore::create(columns);
    bool loading=false;
    std::string value() {return buffer->get_text().raw();}
    bool dirty() {return !document.path.empty() && value()!=document.text;}
    void message(const std::string& s) {status.pop();status.push(s);}
    void update_title() {
        auto name=document.path.empty()?vault.root.filename().string():fs::path(document.path).filename().string();
        if(!document.path.empty()) name.resize(name.size()-3);
        set_title(name+(dirty()?" *":"")+" — Notes");
    }
    void position() {
        if(reading) {message("Reading");return;}
        auto at=buffer->get_iter_at_mark(buffer->get_insert());
        message("Ln "+std::to_string(at.get_line()+1)+", Col "+std::to_string(at.get_line_offset()+1));
    }
    void focus_content() {if(reading) reading_view.grab_focus();else editor.grab_focus();}
    void refresh_reading() {
        rendered=document.path.empty()?Render{}:vault.render(document.path,value());
        reading_buffer->set_text(rendered.text);
        for(auto& s:rendered.spans) reading_buffer->apply_tag(reading_tags.at(s.style),reading_buffer->get_iter_at_offset(s.start),reading_buffer->get_iter_at_offset(s.end));
        place_reading_caret();
    }
    void place_reading_caret() {
        int line=buffer->get_iter_at_mark(buffer->get_insert()).get_line()+1,offset=0;
        for(auto& block:rendered.blocks) {if(block.line>line) break;offset=block.offset;}
        auto at=reading_buffer->get_iter_at_offset(offset);reading_buffer->place_cursor(at);
        // A newly shown stack child has not yet laid out the new text. Scroll
        // after GTK's resize/validation work, using the final insert mark.
        reading_scroll_pending=true;
        reading_scrolling.disconnect();
        reading_scrolling=Glib::signal_idle().connect(sigc::mem_fun(*this,&Window::scroll_reading_caret));
    }
    bool scroll_reading_caret() {
        if(reading && reading_view.get_mapped() && reading_view.get_allocated_height()>1) {
            reading_scroll_pending=false;
            auto at=reading_buffer->get_iter_at_mark(reading_buffer->get_insert());
            reading_view.scroll_to(at,0.1,0.0,0.0);
        }
        return false;
    }
    void toggle_reading() {
        reading=!reading;
        views.set_visible_child(reading?"reading":"editor");
        if(reading) refresh_reading();
        focus_content();position();
    }
    void follow_reading(int offset) {
        for(auto& l:rendered.links) if(l.start<=offset&&offset<l.end) {
            auto parsed=parse(l.raw);if(parsed.empty()) return;auto link=parsed.front();
            try {
                if(l.resolved&&!is_note(*l.resolved)) {message("Not a note: "+*l.resolved);return;}
                if(!save()) return;
                auto path=l.resolved;
                if(!path) {auto created=vault.create(link.target);path=created.first;refresh_tree();}
                open_note(*path,link.heading);
            } catch(const std::exception& e) {message(std::string("refused: ")+e.what());}
            return;
        }
    }
    void follow_current() {
        if(reading) follow_reading(reading_buffer->get_iter_at_mark(reading_buffer->get_insert()).get_offset());
        else follow(buffer->get_iter_at_mark(buffer->get_insert()).get_offset());
    }
    bool save() {
        if(document.path.empty()) return true;
        try {document.save(vault,value());refresh_u2();update_title();position();return true;}
        catch(const std::exception& e) {message(e.what());return false;}
    }
    void refresh_tree() {
        store->clear(); std::map<std::string,Gtk::TreeModel::iterator> folders;
        for(auto& path:vault.directories()) {
            auto parent=folders.find(fs::path(path).parent_path().generic_string());
            auto row=parent==folders.end()?store->append():store->append(parent->second->children());
            (*row)[columns.label]=fs::path(path).filename().string(); (*row)[columns.path]="";
            folders[path]=row;
        }
        for(auto& path:vault.notes()) {
            auto parent=folders.find(fs::path(path).parent_path().generic_string());
            auto row=parent==folders.end()?store->append():store->append(parent->second->children());
            (*row)[columns.label]=fs::path(path).filename().string(); (*row)[columns.path]=path;
        }
        tree.expand_all();select_note();
    }
    void select_note() {
        std::function<bool(const Gtk::TreeModel::Children&)> visit;
        visit=[&](const Gtk::TreeModel::Children& children) {
            for(auto row=children.begin();row!=children.end();++row) {
                if(Glib::ustring((*row)[columns.path]).raw()==document.path&&!document.path.empty()) {
                    auto path=store->get_path(row);tree.expand_to_path(path);
                    tree.get_selection()->select(row);tree.scroll_to_row(path);return true;
                }
                if(visit(row->children())) return true;
            }
            return false;
        };
        visit(store->children());
    }
    void style_links() {
        styling.disconnect();
        buffer->remove_tag(resolved_tag,buffer->begin(),buffer->end());
        buffer->remove_tag(unresolved_tag,buffer->begin(),buffer->end());
        if(document.path.empty()) return;
        try {for(auto& l:vault.links(document.path,value())) {
            buffer->apply_tag(l.resolved?resolved_tag:unresolved_tag,buffer->get_iter_at_offset(l.offset),buffer->get_iter_at_offset(l.offset+l.length));
        }} catch(const std::exception& e) {message(e.what());}
    }
    void refresh_u2() {
        select_note();tag_store->clear();backlink_store->clear();
        try {
            for(auto& t:vault.tags()) {
                auto row=tag_store->append();(*row)[columns.label]=t.tag+" ("+std::to_string(t.count)+")";
                for(auto& path:vault.tagged(t.tag)) {
                    auto child=tag_store->append(row->children());(*child)[columns.label]=path;(*child)[columns.path]=path;
                }
            }
            if(!document.path.empty()) for(auto& b:vault.backlinks(document.path)) {
                auto row=backlink_store->append();(*row)[columns.label]=b.source+" (line "+std::to_string(b.line)+")";(*row)[columns.text]=b.text;
                (*row)[columns.path]=b.source;(*row)[columns.line]=b.line;(*row)[columns.col]=b.col;
            }
        } catch(const std::exception& e) {message(e.what());}
        style_links();
    }
    void jump(int line,int col) {
        auto at=buffer->get_iter_at_line(line-1);at.forward_chars(col-1);
        buffer->place_cursor(at);editor.scroll_to(at,0.1);if(reading) place_reading_caret();focus_content();position();
    }
    void open_backlink() {
        auto row=backlinks_tree.get_selection()->get_selected();if(!row) return;
        auto path=Glib::ustring((*row)[columns.path]).raw();int line=(*row)[columns.line],col=(*row)[columns.col];
        if(open_note(path)) jump(line,col);
    }
    void search_dialog() {
        Gtk::Dialog dialog("Search",*this,true);dialog.set_default_size(640,360);
        Gtk::Entry entry;Gtk::ScrolledWindow scroll;Gtk::TreeView results;
        auto matches=Gtk::ListStore::create(columns);
        results.set_model(matches);results.append_column("Matches",columns.label);results.set_headers_visible(false);
        scroll.add(results);scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        dialog.get_content_area()->pack_start(entry,Gtk::PACK_SHRINK);dialog.get_content_area()->pack_start(scroll);
        auto update=[&]() {
            matches->clear();
            try {if(!entry.get_text().empty()) for(auto& m:vault.find(entry.get_text().raw())) {
                auto row=matches->append();(*row)[columns.label]=m.path+":"+std::to_string(m.line)+": "+m.text;
                (*row)[columns.path]=m.path;(*row)[columns.line]=m.line;(*row)[columns.col]=m.col;
            }} catch(const std::exception& e) {message(e.what());}
            if(!matches->children().empty()) results.get_selection()->select(matches->children().begin());
        };
        entry.signal_changed().connect(update);
        entry.signal_activate().connect([&]{dialog.response(Gtk::RESPONSE_OK);});
        results.signal_row_activated().connect([&](const Gtk::TreeModel::Path&,Gtk::TreeViewColumn*){dialog.response(Gtk::RESPONSE_OK);});
        dialog.signal_key_press_event().connect([&](GdkEventKey* event) {
            if(event->keyval==GDK_KEY_Escape) {dialog.response(Gtk::RESPONSE_CANCEL);return true;}
            if(event->keyval==GDK_KEY_Return||event->keyval==GDK_KEY_KP_Enter) {dialog.response(Gtk::RESPONSE_OK);return true;}
            if(event->keyval==GDK_KEY_Down||event->keyval==GDK_KEY_Up) {
                auto row=results.get_selection()->get_selected();if(row) {
                    if(event->keyval==GDK_KEY_Down) {auto next=row;++next;if(next!=matches->children().end()) row=next;}
                    else if(row!=matches->children().begin()) --row;
                    results.get_selection()->select(row);results.scroll_to_row(matches->get_path(row));
                }return true;
            }
            return false;
        },false);
        dialog.show_all();entry.grab_focus();auto response=dialog.run();dialog.hide();
        if(response==Gtk::RESPONSE_OK) {
            auto row=results.get_selection()->get_selected();if(row) {
                auto path=Glib::ustring((*row)[columns.path]).raw();int line=(*row)[columns.line],col=(*row)[columns.col];
                if(open_note(path)) jump(line,col);
            }
        }
        focus_content();
    }
    void rename_dialog() {
        if(document.path.empty()) return;
        Gtk::Dialog dialog("Rename",*this,true);Gtk::Entry entry;
        entry.set_text(document.path.substr(0,document.path.size()-3));entry.select_region(0,-1);
        dialog.get_content_area()->pack_start(entry);dialog.set_default_size(440,90);
        entry.signal_activate().connect([&]{dialog.response(Gtk::RESPONSE_OK);});
        dialog.signal_key_press_event().connect([&](GdkEventKey* event) {
            if(event->keyval==GDK_KEY_Escape) {dialog.response(Gtk::RESPONSE_CANCEL);return true;}
            return false;
        },false);
        dialog.show_all();entry.grab_focus();auto response=dialog.run();dialog.hide();
        if(response==Gtk::RESPONSE_OK) {
            int offset=buffer->get_iter_at_mark(buffer->get_insert()).get_offset();
            try {
                document.save(vault,value());update_title();
                auto result=vault.rename(document.path,entry.get_text().raw());
                offset=result.map_caret(offset);
                // The current note can itself have rewritten links. Reload its new bytes
                // without attempting to save the pre-rename document stamp.
                document=Document{};
                refresh_tree();
                if(open_note(result.to)) {
                    auto at=buffer->get_iter_at_offset(std::min(offset,buffer->get_char_count()));
                    buffer->place_cursor(at);editor.scroll_to(at,0.1);if(reading) place_reading_caret();position();
                }
            } catch(const std::exception& e) {refresh_u2();message(std::string("Rename refused: ")+e.what());}
        }
        focus_content();
    }
    bool open_note(const std::string& path, const Maybe& heading={}) {
        if(!save()) return false;
        try {
            Document next; next.load(vault,path); document=next;
            loading=true;
            // A loaded note starts a new history; only subsequent edits are undoable.
            buffer->begin_not_undoable_action();
            buffer->set_text(document.text);
            buffer->end_not_undoable_action();
            buffer->set_modified(false);loading=false;
            int offset=heading?heading_offset(document.text,*heading):0;
            auto iter=buffer->get_iter_at_offset(offset);buffer->place_cursor(iter);
            editor.set_sensitive(true);editor.scroll_to(iter,0.1);if(reading) refresh_reading();focus_content();refresh_u2();update_title();position();return true;
        } catch(const std::exception& e) {message(e.what());return false;}
    }
    void follow(int offset, bool clicked=false) {
        if(document.path.empty()) return;
        try {
            for(auto& l:vault.links(document.path,value())) {
                if(offset<l.offset || (!clicked && offset==l.offset) || offset>=l.offset+l.length) continue;
                if(l.resolved && !is_note(*l.resolved)) {message("Not a note: "+*l.resolved);return;}
                if(!save()) return;
                auto path=l.resolved;
                if(!path) {auto created=vault.create(l.target);path=created.first;refresh_tree();}
                open_note(*path,l.heading);return;
            }
        } catch(const std::exception& e) {message(std::string("refused: ")+e.what());}
    }
    void switcher() {
        Gtk::Dialog dialog("Quick Switcher",*this,true);
        dialog.set_default_size(480,340);
        Gtk::Entry entry;
        Gtk::ScrolledWindow scroll;
        Gtk::TreeView results;
        auto matches=Gtk::ListStore::create(columns);
        results.set_model(matches);results.append_column("Note",columns.label);results.set_headers_visible(false);
        scroll.add(results);scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        auto box=dialog.get_content_area();box->pack_start(entry,Gtk::PACK_SHRINK);box->pack_start(scroll);
        auto update=[&]() {
            matches->clear();
            try {for(auto& path:vault.search(entry.get_text().raw())) {
                auto row=matches->append();(*row)[columns.label]=path;(*row)[columns.path]=path;
            }} catch(const std::exception& e) {message(e.what());}
            auto first=matches->children().begin();if(first!=matches->children().end()) results.get_selection()->select(first);
        };
        entry.signal_changed().connect(update);
        entry.signal_activate().connect([&](){dialog.response(Gtk::RESPONSE_OK);});
        results.signal_row_activated().connect([&](const Gtk::TreeModel::Path&,Gtk::TreeViewColumn*){dialog.response(Gtk::RESPONSE_OK);});
        dialog.signal_key_press_event().connect([&](GdkEventKey* event) {
            if(event->keyval==GDK_KEY_Escape) {dialog.response(Gtk::RESPONSE_CANCEL);return true;}
            if(event->keyval==GDK_KEY_Return || event->keyval==GDK_KEY_KP_Enter) {dialog.response(Gtk::RESPONSE_OK);return true;}
            if(event->keyval==GDK_KEY_Down || event->keyval==GDK_KEY_Up) {
                auto selected=results.get_selection()->get_selected();
                if(selected) {
                    if(event->keyval==GDK_KEY_Down) {auto next=selected;++next;if(next!=matches->children().end()) selected=next;}
                    else if(selected!=matches->children().begin()) --selected;
                    results.get_selection()->select(selected);results.scroll_to_row(matches->get_path(selected));
                }
                return true;
            }
            return false;
        },false);
        update();dialog.show_all();entry.grab_focus();
        int response=dialog.run();dialog.hide();
        if(response==Gtk::RESPONSE_OK) {
            try {
                auto row=results.get_selection()->get_selected();
                if(row) open_note(Glib::ustring((*row)[columns.path]).raw());
                else if(save()) {auto created=vault.create(entry.get_text().raw());refresh_tree();open_note(created.first);}
            } catch(const std::exception& e) {message(std::string("refused: ")+e.what());}
        }
        focus_content();
    }
    bool key(GdkEventKey* event) {
        bool ctrl=event->state&GDK_CONTROL_MASK,alt=event->state&GDK_MOD1_MASK;
        bool shift=event->state&GDK_SHIFT_MASK;
        if(event->keyval==GDK_KEY_F2) {rename_dialog();return true;}
        if(ctrl&&shift&&(event->keyval==GDK_KEY_f||event->keyval==GDK_KEY_F)) {search_dialog();return true;}
        if(ctrl&&shift&&(event->keyval==GDK_KEY_b||event->keyval==GDK_KEY_B)) {
            if(!backlink_store->children().empty()) backlinks_tree.get_selection()->select(backlink_store->children().begin());
            backlinks_tree.grab_focus();return true;
        }
        if(ctrl && (event->keyval==GDK_KEY_e || event->keyval==GDK_KEY_E)) {toggle_reading();return true;}
        if(reading && ctrl&&(event->keyval==GDK_KEY_z||event->keyval==GDK_KEY_Z||event->keyval==GDK_KEY_y||event->keyval==GDK_KEY_Y)) return true;
        bool enter=event->keyval==GDK_KEY_Return || event->keyval==GDK_KEY_KP_Enter;
        if(reading && reading_view.has_focus() && enter) {
            follow_current();
            return true;
        }
        if(ctrl && (event->keyval==GDK_KEY_s || event->keyval==GDK_KEY_S)) {if(!reading) save();return true;}
        if(ctrl && (event->keyval==GDK_KEY_o || event->keyval==GDK_KEY_O)) {switcher();return true;}
        if(alt && enter && !reading && editor.has_focus()) {follow_current();return true;}
        return false;
    }
    void menu(const Glib::ustring& name,const std::vector<std::pair<std::string,std::function<void()>>>& actions) {
        auto item=Gtk::manage(new Gtk::MenuItem(name,true));auto submenu=Gtk::manage(new Gtk::Menu);
        item->set_submenu(*submenu);menubar.append(*item);
        for(auto& action:actions) {
            auto child=Gtk::manage(new Gtk::MenuItem(action.first,true));child->signal_activate().connect(action.second);submenu->append(*child);
        }
    }
protected:
    bool on_delete_event(GdkEventAny*) override {
        if(save()) return false;
        Gtk::MessageDialog dialog(*this,"The note could not be saved. Discard changes?",false,Gtk::MESSAGE_WARNING,Gtk::BUTTONS_NONE,true);
        dialog.set_secondary_text("Your text will remain in the editor if you cancel.");
        dialog.add_button("_Discard",Gtk::RESPONSE_REJECT);dialog.add_button("_Cancel",Gtk::RESPONSE_CANCEL);
        dialog.set_default_response(Gtk::RESPONSE_CANCEL);
        return dialog.run()!=Gtk::RESPONSE_REJECT;
    }
public:
    Window(const fs::path& root,const std::string& note):vault(root) {
        // Select the monitor at the pointer before mapping, then refine using the
        // actual WM frame once decorations have been installed.
        auto display=gdk_display_get_default();
        auto pointer=gdk_seat_get_pointer(gdk_display_get_default_seat(display));
        int px=0,py=0;gdk_device_get_position(pointer,nullptr,&px,&py);
        auto monitor=gdk_display_get_monitor_at_point(display,px,py);
        GdkRectangle area;gdk_monitor_get_workarea(monitor,&area);
        bool compact=area.width<1200||area.height<780;
        int width=compact?std::max(640,std::min(1100,area.width-16)):1100;
        int height=compact?std::max(480,std::min(650,area.height-40)):650;
        set_default_size(width,height);move(area.x,area.y);add(layout);
        signal_map_event().connect([this](GdkEventAny*) {
            if(!initial_geometry_pending) return false;
            initial_geometry_pending=false;
            Glib::signal_timeout().connect_once([this] {
                auto window=get_window();if(!window) return;
                auto monitor=gdk_display_get_monitor_at_window(gdk_display_get_default(),window->gobj());
                GdkRectangle area;gdk_monitor_get_workarea(monitor,&area);
                Gdk::Rectangle frame;window->get_frame_extents(frame);
                int w,h;get_size(w,h);
                int dw=std::max(0,frame.get_width()-w),dh=std::max(0,frame.get_height()-h);
                bool compact=area.width<1200||area.height<780;
                int width=compact?std::max(640,std::min(1100,area.width-dw)):1100;
                int height=compact?std::max(480,std::min(650,area.height-dh)):650;
                resize(width,height);
                move(area.x+std::max(0,(area.width-width-dw)/2),area.y+std::max(0,(area.height-height-dh)/2));
                content.set_position(std::max(100,width-panes.get_position()-312));
            },100);
            return false;
        });
        menu("_File",{{"Quick Switcher (Ctrl+O)",[this]{switcher();}},{"Save (Ctrl+S)",[this]{if(!reading) save();}},{"_Rename… (F2)",[this]{rename_dialog();}},{"_Quit",[this]{close();}}});
        menu("_Edit",{{"_Undo",[this]{if(!reading&&buffer->can_undo()) buffer->undo();}},{"_Redo",[this]{if(!reading&&buffer->can_redo()) buffer->redo();}},{"Cu_t",[this]{if(!reading) buffer->cut_clipboard(Gtk::Clipboard::get());}},{"_Copy",[this]{if(reading) reading_buffer->copy_clipboard(Gtk::Clipboard::get());else buffer->copy_clipboard(Gtk::Clipboard::get());}},{"_Paste",[this]{if(!reading) buffer->paste_clipboard(Gtk::Clipboard::get());}}});
        menu("_View",{{"_Reading View (Ctrl+E)",[this]{toggle_reading();}},{"Focus _Editor",[this]{focus_content();}}});
        menu("_Go",{{"Quick _Switcher",[this]{switcher();}},{"Follow _Link",[this]{follow_current();}}});
        menu("_Help",{{"_About",[this]{Gtk::AboutDialog dialog;dialog.set_transient_for(*this);dialog.set_program_name("LCOS Notes");dialog.set_version("0.4.0");dialog.set_copyright("Copyright 2026 Lee Harrington");dialog.set_license_type(Gtk::LICENSE_CUSTOM);dialog.set_wrap_license(true);dialog.set_license("Licensed under the Apache License, Version 2.0 (the \"License\"); you may not use this program except in compliance with the License. You may obtain a copy of the License at https://www.apache.org/licenses/LICENSE-2.0\n\nUnless required by applicable law or agreed to in writing, software distributed under the License is distributed on an \"AS IS\" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.");dialog.set_comments("Offline Markdown notes for LCOS and X11 desktops. Apache-2.0.");dialog.run();}}});
        layout.pack_start(menubar,Gtk::PACK_SHRINK);layout.pack_start(panes);layout.pack_end(status,Gtk::PACK_SHRINK);
        tree.set_model(store);tree.append_column("Notes",columns.label);tree.set_headers_visible(false);
        tree_scroll.add(tree);tree_scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        sidebar.append_page(tree_scroll,"Notes");sidebar.append_page(tags_scroll,"Tags");
        panes.pack1(sidebar,false,false);panes.pack2(content,true,false);panes.set_position(190);
        content.pack1(views,true,false);content.pack2(backlinks_scroll,false,false);content.set_position(std::max(100,width-502));
        tags_tree.set_model(tag_store);tags_tree.append_column("Tags",columns.label);tags_tree.set_headers_visible(false);
        tags_scroll.add(tags_tree);tags_scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        backlinks_tree.set_model(backlink_store);backlinks_tree.append_column("Source",columns.label);
        backlinks_tree.append_column("Text",columns.text);
        for(auto column:backlinks_tree.get_columns()) column->set_resizable(true);
        backlinks_scroll.add(backlinks_tree);backlinks_scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        backlinks_scroll.set_size_request(300,-1);
        backlinks_tree.signal_row_activated().connect([this](const Gtk::TreeModel::Path&,Gtk::TreeViewColumn*){open_backlink();});
        tags_tree.signal_row_activated().connect([this](const Gtk::TreeModel::Path& path,Gtk::TreeViewColumn*) {
            auto row=tag_store->get_iter(path);auto note=Glib::ustring((*row)[columns.path]).raw();if(!note.empty()) open_note(note);
        });
        buffer->set_language(Gsv::LanguageManager::get_default()->get_language("markdown"));
        buffer->set_highlight_syntax(true);
        resolved_tag=buffer->create_tag("wikilink-resolved");resolved_tag->property_foreground()="#205ca8";resolved_tag->property_underline()=Pango::UNDERLINE_SINGLE;
        unresolved_tag=buffer->create_tag("wikilink-unresolved");unresolved_tag->property_foreground()="#a33b24";unresolved_tag->property_underline()=Pango::UNDERLINE_SINGLE;
        editor.set_buffer(buffer);editor.set_show_line_numbers(true);editor.set_wrap_mode(Gtk::WRAP_WORD_CHAR);editor.set_monospace(true);
        editor_scroll.add(editor);editor_scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        views.add(editor_scroll,"editor");views.add(reading_scroll,"reading");
        reading_view.set_buffer(reading_buffer);reading_view.set_editable(false);reading_view.set_cursor_visible(true);
        reading_view.signal_size_allocate().connect([this](Gtk::Allocation&) {
            if(reading_scroll_pending) scroll_reading_caret();
        });
        reading_view.set_wrap_mode(Gtk::WRAP_WORD_CHAR);reading_view.set_left_margin(12);reading_view.set_right_margin(12);reading_scroll.add(reading_view);
        reading_scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        for(auto name:{"h1","h2","h3","h4","h5","h6","em","strong","code","codeblock","quote","url","link","unresolved","rule"}) reading_tags[name]=reading_buffer->create_tag(name);
        for(int i=1;i<=6;++i) {auto tag=reading_tags["h"+std::to_string(i)];tag->property_weight()=Pango::WEIGHT_BOLD;tag->property_scale()=1.7-0.1*i;}
        reading_tags["em"]->property_style()=Pango::STYLE_ITALIC;
        reading_tags["strong"]->property_weight()=Pango::WEIGHT_BOLD;
        for(auto name:{"code","codeblock"}) {reading_tags[name]->property_family()="monospace";reading_tags[name]->property_background()="#eeeeea";}
        reading_tags["quote"]->property_left_margin()=36;reading_tags["quote"]->property_foreground()="#666666";
        reading_tags["rule"]->property_foreground()="#666666";
        for(auto name:{"url","link","unresolved"}) {reading_tags[name]->property_underline()=Pango::UNDERLINE_SINGLE;reading_tags[name]->property_foreground()=std::string(name)=="unresolved"?"#a33b24":"#205ca8";}
        reading_view.signal_button_press_event().connect([this](GdkEventButton* event) {
            if(event->button!=1 || (event->state&(GDK_SHIFT_MASK|GDK_CONTROL_MASK|GDK_MOD1_MASK))) return false;
            int x,y;reading_view.window_to_buffer_coords(reading_view.get_window_type(Glib::wrap(event->window,true)),event->x,event->y,x,y);
            Gtk::TextBuffer::iterator at;int trailing;reading_view.get_iter_at_position(at,trailing,x,y);
            // A click past the line's text must not follow the last link on it.
            Gdk::Rectangle rect;reading_view.get_iter_location(at,rect);
            if(x<rect.get_x()||x>=rect.get_x()+rect.get_width()||y<rect.get_y()||y>=rect.get_y()+rect.get_height()) return false;
            for(auto& l:rendered.links) if(l.start<=at.get_offset()&&at.get_offset()<l.end) {follow_reading(at.get_offset());return true;}
            return false;
        },false);
        editor.set_sensitive(false);
        tree.signal_row_activated().connect([this](const Gtk::TreeModel::Path& path,Gtk::TreeViewColumn*) {
            auto row=store->get_iter(path);auto s=Glib::ustring((*row)[columns.path]).raw();if(!s.empty()) open_note(s);
        });
        buffer->signal_changed().connect([this]{if(!loading) {
            update_title();styling.disconnect();
            styling=Glib::signal_timeout().connect([this]{style_links();return false;},180);
        }});
        // Cursor-position notifications include edits that move the insert mark without mark-set.
        buffer->property_cursor_position().signal_changed().connect([this]{position();});
        signal_key_press_event().connect(sigc::mem_fun(*this,&Window::key),false);
        editor.signal_button_press_event().connect([this](GdkEventButton* event) {
            if(event->button!=1 || !(event->state&GDK_CONTROL_MASK)) return false;
            int x,y; editor.window_to_buffer_coords(editor.get_window_type(Glib::wrap(event->window,true)),event->x,event->y,x,y);
            Gtk::TextBuffer::iterator at;editor.get_iter_at_location(at,x,y);follow(at.get_offset(),true);return true;
        },false);
        refresh_tree();refresh_u2();show_all_children();views.set_visible_child("editor");update_title();position();
        if(!note.empty()) {editor.set_sensitive(true);open_note(note);}
        auto config=fs::path(Glib::get_user_config_dir())/"lcos-notes";
        fs::create_directories(config);std::ofstream(config/"last-vault")<<vault.root.string()<<'\n';
    }
};
int main(int argc,char** argv) {
    if(!g_getenv("GDK_BACKEND")) g_setenv("GDK_BACKEND","x11",false);
    g_setenv("GTK_CSD","0",true);
    try {
        std::string root,note;
        for(int i=1;i<argc;++i) {
            std::string arg=argv[i];
            if(arg=="--vault" && i+1<argc && root.empty()) root=argv[++i];
            else if(arg.size() && arg[0]!='-' && note.empty()) note=arg;
            else throw std::runtime_error("usage: lcos-notes [--vault DIR [NOTE]]");
        }
        auto app=Gtk::Application::create("com.leebase.LcosNotes",Gio::APPLICATION_NON_UNIQUE);Gsv::init();
        Gtk::Settings::get_default()->property_gtk_dialogs_use_header()=false;
        if(root.empty()) {
            std::ifstream last(fs::path(Glib::get_user_config_dir())/"lcos-notes"/"last-vault");std::getline(last,root);
            if(!fs::is_directory(root)) {
                Gtk::FileChooserDialog chooser("Open Vault",Gtk::FILE_CHOOSER_ACTION_SELECT_FOLDER);
                chooser.add_button("_Cancel",Gtk::RESPONSE_CANCEL);chooser.add_button("_Open",Gtk::RESPONSE_OK);
                if(chooser.run()!=Gtk::RESPONSE_OK) return 0;
                root=chooser.get_filename();
            }
        }
        Window window(root,note);return app->run(window);
    } catch(const std::exception& e) {std::cerr<<"refused: "<<e.what()<<'\n';return 2;}
}
