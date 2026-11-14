// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Lee Harrington
#include "core.hpp"
#include <gtkmm.h>
#include <gtksourceviewmm.h>
#include <fstream>
#include <iostream>
#include <map>
#include <set>
#include <sys/inotify.h>
#include <unistd.h>
#include <array>
#include <algorithm>
#include <cerrno>
#include <cstring>
using namespace notes;
static fs::path config_dir() { return fs::path(Glib::get_user_config_dir())/"lcos-notes"; }
static std::vector<std::string> recent_vaults() {
    std::vector<std::string> result;
    auto add=[&](const std::string& path) {
        if(path.empty() || !fs::path(path).is_absolute()) return;
        // Keep stale entries usable for later rejection, but collapse aliases of
        // existing directories before deduplication and applying the limit.
        std::error_code error;
        auto canonical=fs::canonical(path,error);
        auto normalized=!error && fs::is_directory(canonical,error) && !error
            ? canonical.string() : path;
        if(std::find(result.begin(),result.end(),normalized)==result.end() && result.size()<10)
            result.push_back(normalized);
    };
    std::ifstream history(config_dir()/"recent-vaults");
    std::string line; while(std::getline(history,line)) add(line);
    std::ifstream last(config_dir()/"last-vault"); std::getline(last,line); add(line);
    return result;
}
static void write_config_file(const fs::path& path,const std::string& contents) {
    GError* error=nullptr;
    if(!g_file_set_contents(path.c_str(),contents.c_str(),contents.size(),&error)) {
        std::string why=error?error->message:"unknown error";
        if(error) g_error_free(error);
        throw std::runtime_error(why);
    }
}
static void remember_vault(const fs::path& root) {
    auto paths=recent_vaults(); auto path=root.string();
    paths.erase(std::remove(paths.begin(),paths.end(),path),paths.end());
    paths.insert(paths.begin(),path); if(paths.size()>10) paths.resize(10);
    std::string history; for(const auto& item:paths) history+=item+"\n";
    fs::create_directories(config_dir());
    auto history_path=config_dir()/"recent-vaults";
    bool had_history=fs::exists(history_path);
    std::string previous;
    if(had_history) {
        std::ifstream input(history_path,std::ios::binary);
        if(!input) throw std::runtime_error("Cannot read existing vault history");
        previous.assign(std::istreambuf_iterator<char>(input),std::istreambuf_iterator<char>());
        if(input.bad()) throw std::runtime_error("Cannot read existing vault history");
    }
    write_config_file(history_path,history);
    try { write_config_file(config_dir()/"last-vault",path+"\n"); }
    catch(...) {
        try {
            if(had_history) write_config_file(history_path,previous);
            else fs::remove(history_path);
        } catch(...) { /* Preserve the original failure; rollback may also fail. */ }
        throw;
    }
}
static fs::path prepare_vault(const fs::path& path) {
    auto root=fs::canonical(path);
    struct stat st{};
    if(stat(root.c_str(),&st)!=0 || !S_ISDIR(st.st_mode)) throw std::runtime_error("Not a directory");
    if(!(st.st_mode&0444) || !(st.st_mode&0111) || access(root.c_str(),R_OK|X_OK)!=0)
        throw std::runtime_error("Vault is not readable or traversable");
    Vault candidate(root); candidate.files(); candidate.directories();
    return root;
}
class Window : public Gtk::Window {
    Vault vault;
    Document document;
    Gtk::Box layout{Gtk::ORIENTATION_VERTICAL};
    Gtk::MenuBar menubar;
    Gtk::Paned panes{Gtk::ORIENTATION_HORIZONTAL};
    Gtk::ScrolledWindow tree_scroll, editor_scroll, tags_scroll, backlinks_scroll, mentions_scroll, outline_scroll;
    Gtk::TreeView outline_tree;
    Gtk::Box backlinks_box{Gtk::ORIENTATION_VERTICAL},backlinks_upper{Gtk::ORIENTATION_VERTICAL},mentions_lower{Gtk::ORIENTATION_VERTICAL};
    Gtk::Paned backlinks_split{Gtk::ORIENTATION_VERTICAL};
    Gtk::Label backlinks_label{"Backlinks"},mentions_label{"Unlinked mentions"};
    Gtk::TreeView mentions_tree;
    Gtk::CheckMenuItem* reading_item=nullptr;
    Gtk::Notebook sidebar;
    Gtk::Stack views;
    Gtk::ScrolledWindow reading_scroll;
    Gtk::Box reading_container{Gtk::ORIENTATION_VERTICAL}, properties_box{Gtk::ORIENTATION_VERTICAL};
    Gtk::TextView reading_view;
    Glib::RefPtr<Gtk::TextBuffer> reading_buffer=Gtk::TextBuffer::create();
    std::map<std::string,Glib::RefPtr<Gtk::TextTag>> reading_tags;
    Render rendered;
    struct ReadingImage { Gtk::Image* widget; Glib::RefPtr<Gdk::Pixbuf> pixbuf; int extra_margin; int offset; };
    std::vector<ReadingImage> reading_images;
    std::vector<bool> fold_closed;
    std::map<int,Glib::RefPtr<Gtk::TextTag>> margin_tags;
    int extra_margin(int offset) const {
        int margin=0;
        for(const auto& span:rendered.layout_spans)
            if(span.start<=offset&&offset<span.end) margin+=24;
        return margin;
    }
    void update_folds() {
        reading_buffer->remove_tag(reading_tags.at("folded"),reading_buffer->begin(),reading_buffer->end());
        size_t index=0;
        for(const auto& span:rendered.spans) if(span.style=="folded") {
            if(fold_closed[index]) reading_buffer->apply_tag(reading_tags.at("folded"),
                reading_buffer->get_iter_at_offset(span.start),reading_buffer->get_iter_at_offset(span.end));
            ++index;
        }
    }
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
    Gtk::Label vault_label;
    struct Columns : Gtk::TreeModel::ColumnRecord {
        Gtk::TreeModelColumn<Glib::ustring> label,path,text;
        Gtk::TreeModelColumn<int> line,col;
        Columns(){add(label);add(path);add(text);add(line);add(col);}
    } columns;
    Glib::RefPtr<Gtk::TreeStore> store=Gtk::TreeStore::create(columns);
    Glib::RefPtr<Gtk::TreeStore> tag_store=Gtk::TreeStore::create(columns);
    Glib::RefPtr<Gtk::ListStore> outline_store=Gtk::ListStore::create(columns);
    Glib::RefPtr<Gtk::ListStore> backlink_store=Gtk::ListStore::create(columns);
    Glib::RefPtr<Gtk::ListStore> mention_store=Gtk::ListStore::create(columns);
    bool loading=false;
    int notify_fd=-1;
    sigc::connection notify_connection, external_pending;
    std::map<int,std::string> watches;
    using DiskState=std::map<std::string,std::array<long long,6>>;
    DiskState disk_state;
    DiskState scan_disk() {
        DiskState state;
        auto paths=vault.files();auto dirs=vault.directories();paths.insert(paths.end(),dirs.begin(),dirs.end());
        for(auto& path:paths) {
            struct stat st{};if(lstat((vault.root/path).c_str(),&st)!=0) continue;
            state[path]=S_ISDIR(st.st_mode)?std::array<long long,6>{st.st_ino,0,0,0,0,0}:std::array<long long,6>{st.st_ino,st.st_size,st.st_mtim.tv_sec,st.st_mtim.tv_nsec,st.st_ctim.tv_sec,st.st_ctim.tv_nsec};
        }
        return state;
    }
    void watch_directories() {
        if(notify_fd<0) return;
        std::set<std::string> dirs{std::string{}};
        for(auto& p:vault.directories()) dirs.insert(p);
        for(auto it=watches.begin();it!=watches.end();) {
            if(!dirs.count(it->second)) {inotify_rm_watch(notify_fd,it->first);it=watches.erase(it);} else ++it;
        }
        for(auto& dir:dirs) {
            bool exists=false;for(auto& w:watches) if(w.second==dir) exists=true;
            if(exists) continue;
            int id=inotify_add_watch(notify_fd,(vault.root/dir).c_str(),IN_CREATE|IN_DELETE|IN_MOVED_FROM|IN_MOVED_TO|IN_MODIFY|IN_CLOSE_WRITE|IN_ATTRIB|IN_DELETE_SELF|IN_MOVE_SELF);
            if(id>=0) watches[id]=dir;
        }
    }
    // Snapshot only following events or app operations, never on a polling timer.
    void own_changes(const std::vector<std::string>& paths={}) {
        auto updated=paths;if(updated.empty()&&!document.path.empty()) updated.push_back(document.path);
        for(auto path:updated) {
            struct stat st{};
            if(lstat((vault.root/path).c_str(),&st)==0)
                disk_state[path]=S_ISDIR(st.st_mode)?std::array<long long,6>{st.st_ino,0,0,0,0,0}:std::array<long long,6>{st.st_ino,st.st_size,st.st_mtim.tv_sec,st.st_mtim.tv_nsec,st.st_ctim.tv_sec,st.st_ctim.tv_nsec};
            else disk_state.erase(path);
            for(auto parent=fs::path(path).parent_path();!parent.empty();parent=parent.parent_path()) {
                if(lstat((vault.root/parent).c_str(),&st)==0&&S_ISDIR(st.st_mode)) disk_state[parent.generic_string()]={st.st_ino,0,0,0,0,0};
            }
        }
        watch_directories();
    }
    void reload_disk() {
        if(document.path.empty()) return;
        auto at=buffer->get_iter_at_mark(buffer->get_insert());int line=at.get_line(),col=at.get_line_offset();
        int reading_offset=reading_buffer->get_iter_at_mark(reading_buffer->get_insert()).get_offset();
        try {
            Document next;next.load(vault,document.path);document=next;
            loading=true;buffer->begin_not_undoable_action();buffer->set_text(document.text);buffer->end_not_undoable_action();buffer->set_modified(false);loading=false;
            line=std::min(line,buffer->get_line_count()-1);at=buffer->get_iter_at_line(line);
            int length=0;if(!at.ends_line()) {auto end=at;end.forward_to_line_end();length=end.get_line_offset();}
            at.forward_chars(std::min(col,length));buffer->place_cursor(at);editor.scroll_to(at,0.1);
            refresh_u2(nullptr,true);if(reading) {refresh_reading();reading_buffer->place_cursor(reading_buffer->get_iter_at_offset(std::min(reading_offset,reading_buffer->get_char_count())));}
            update_title();message("Reloaded: changed on disk");
        } catch(const std::exception& e) {loading=false;message(std::string("refused: ")+e.what());}
    }
    bool external_changes() {
        auto current=scan_disk();watch_directories();
        // An external writer may replace the open file between our save and
        // recording its directory state; the Document stamp remains authoritative.
        if(current==disk_state&&(document.path.empty()||!document.changed(vault))) return false;
        disk_state=std::move(current);
        refresh_tree(true);refresh_u2(nullptr,true);
        if(!document.path.empty()&&document.changed(vault)) {
            std::error_code ec;
            if(!fs::exists(vault.root/document.path,ec)) {
                document.mark_deleted();buffer->set_modified(true);update_title();message("Deleted on disk");
            } else if(dirty()) {
                bool merged=false;
                try {Document next;next.load(vault,document.path);const auto& old=document.text;const auto& updated=next.text;auto first=updated.find('\n');std::string e=first!=std::string::npos&&first>0&&updated[first-1]=='\r'?"\r\n":"\n";std::string prefix=old;if(!prefix.empty()&&prefix.back()!='\n')prefix+=e;
                    if(updated.compare(0,prefix.size(),prefix)==0){auto suffix=updated.substr(prefix.size());bool block=false,ok=!suffix.empty();size_t at=0;while(ok&&at<suffix.size()){auto end=suffix.find(e,at);if(end==std::string::npos){ok=false;break;}auto line=suffix.substr(at,end-at);bool head=line.size()>=7&&line[0]=='-'&&line[1]==' '&&g_ascii_isdigit(line[2])&&g_ascii_isdigit(line[3])&&line[4]==':'&&g_ascii_isdigit(line[5])&&g_ascii_isdigit(line[6])&&(line.size()==7||line[7]==' ');if(head)block=true;else if(!block||(!line.empty()&&line.compare(0,2,"  ")!=0))ok=false;at=end+e.size();}if(ok&&block){auto content=value();auto addition=(content.empty()||content.back()=='\n'?"":e)+suffix;auto insert=buffer->get_iter_at_mark(buffer->get_insert()).get_offset();auto bound=buffer->get_iter_at_mark(buffer->get_selection_bound()).get_offset();buffer->begin_user_action();auto end=buffer->end();buffer->insert(end,addition);buffer->end_user_action();buffer->select_range(buffer->get_iter_at_offset(insert),buffer->get_iter_at_offset(bound));document=next;buffer->set_modified(true);if(reading){int offset=reading_buffer->get_iter_at_mark(reading_buffer->get_insert()).get_offset();refresh_reading();reading_buffer->place_cursor(reading_buffer->get_iter_at_offset(std::min(offset,reading_buffer->get_char_count())));}update_title();message("Captured text added; your unsaved edits are kept");merged=true;}}
                }catch(const std::exception&){}if(!merged)message("Changed on disk; your unsaved edits are kept");
            }
            else reload_disk();
        } else if(reading) {
            int offset=reading_buffer->get_iter_at_mark(reading_buffer->get_insert()).get_offset();
            refresh_reading();reading_buffer->place_cursor(reading_buffer->get_iter_at_offset(std::min(offset,reading_buffer->get_char_count())));
        }
        return false;
    }
    void start_monitoring() {
        notify_fd=inotify_init1(IN_NONBLOCK|IN_CLOEXEC);if(notify_fd<0) {message("Cannot monitor vault");return;}
        disk_state=scan_disk();watch_directories();
        notify_connection=Glib::signal_io().connect([this](Glib::IOCondition) {
            alignas(inotify_event) char bytes[32768];bool relevant=false;ssize_t size;
            while((size=::read(notify_fd,bytes,sizeof bytes))>0) {
                for(char* p=bytes;p<bytes+size;) {
                    auto event=reinterpret_cast<inotify_event*>(p);
                    if(event->mask&IN_IGNORED) watches.erase(event->wd);
                    else {
                        if(event->mask&(IN_MOVE_SELF|IN_DELETE_SELF)) {
                            inotify_rm_watch(notify_fd,event->wd);watches.erase(event->wd);
                        }
                        if(!event->len||event->name[0]!='.') relevant=true;
                    }
                    p+=sizeof(inotify_event)+event->len;
                }
            }
            if(relevant&&!external_pending.connected()) external_pending=Glib::signal_timeout().connect([this]{external_pending.disconnect();return external_changes();},150);
            return true;
        },notify_fd,Glib::IO_IN);
    }
    bool toggle_task(int offset) {
        for(auto t:rendered.tasks) if(t.offset==offset) {
            auto caret=buffer->get_iter_at_mark(buffer->get_insert()).get_offset();
            // GTK also treats U+2029 as a line break. Parser line numbers cannot
            // address its buffer; convert the original byte position to characters.
            auto text=value();
            auto marker=buffer->get_iter_at_offset(g_utf8_pointer_to_offset(text.data(),text.data()+t.source_offset));
            auto end=marker;end.forward_char();buffer->begin_user_action();
            marker=buffer->erase(marker,end);buffer->insert(marker,t.checked?" ":"x");buffer->end_user_action();
            buffer->place_cursor(buffer->get_iter_at_offset(caret));
            refresh_reading();reading_buffer->place_cursor(reading_buffer->get_iter_at_offset(offset));
            reading_view.grab_focus();save();return true;
        }
        return false;
    }
    std::string value() {return buffer->get_text().raw();}
    bool dirty() {return !document.path.empty() && (document.deleted()||value()!=document.text);}
    void message(const std::string& s) {status.pop();status.push(s);}
    void vault_error(const std::string& text) {
        Gtk::MessageDialog dialog(*this,text,false,Gtk::MESSAGE_ERROR,Gtk::BUTTONS_OK,true);
        dialog.run();
    }
    void remember() {
        try { remember_vault(vault.root); }
        catch(const std::exception& e) { vault_error(std::string("Could not save vault history: ")+e.what()); }
    }
    void install_vault(const fs::path& root) {
        notify_connection.disconnect(); external_pending.disconnect(); styling.disconnect(); reading_scrolling.disconnect();
        if(notify_fd>=0) ::close(notify_fd);
        notify_fd=-1; watches.clear(); disk_state.clear();
        document=Document{}; vault=Vault(root);
        loading=true; buffer->begin_not_undoable_action(); buffer->set_text("");
        buffer->end_not_undoable_action(); buffer->set_modified(false); loading=false;
        reading_images.clear(); reading_buffer->set_text(""); rendered=Render{}; fold_closed.clear();
        for(auto child:properties_box.get_children()) properties_box.remove(*child);
        tag_store->clear(); store->clear(); outline_store->clear(); backlink_store->clear(); mention_store->clear();
        if(reading) toggle_reading();
        editor.set_sensitive(false); sidebar.set_current_page(0);
        vault_label.set_text(vault.root.string());
        refresh_tree(); refresh_u2(); update_title(); position(); start_monitoring(); remember();
    }
    void open_vault(const fs::path& path) {
        try {
            auto root=prepare_vault(path);
            if(root==vault.root) return;
            if(!save()) { vault_error("Could not switch vault: the current note was not saved."); return; }
            install_vault(root);
        } catch(const std::exception& e) { vault_error(std::string("Cannot open vault: ")+e.what()); }
    }
    void choose_vault() {
        Gtk::FileChooserDialog dialog(*this,"Open Vault",Gtk::FILE_CHOOSER_ACTION_SELECT_FOLDER);
        dialog.add_button("_Cancel",Gtk::RESPONSE_CANCEL); dialog.add_button("_Open",Gtk::RESPONSE_OK);
        dialog.set_current_folder(vault.root.string());
        std::string typed_path;
        bool composing_unicode=false;
        dialog.signal_key_press_event().connect([&](GdkEventKey* event) {
            if((event->state&GDK_CONTROL_MASK) && (event->state&GDK_SHIFT_MASK) &&
               (event->keyval==GDK_KEY_u || event->keyval==GDK_KEY_U)) {
                composing_unicode=true;
                return false;
            }
            if(event->keyval==GDK_KEY_Escape) composing_unicode=false;
            if(event->keyval!=GDK_KEY_Return && event->keyval!=GDK_KEY_KP_Enter) return false;
            if(composing_unicode) { composing_unicode=false; return false; }
            auto focus=gtk_window_get_focus(GTK_WINDOW(dialog.gobj()));
            if(!focus || !GTK_IS_ENTRY(focus)) return false;
            Glib::ustring text=gtk_entry_get_text(GTK_ENTRY(focus));
            int first=0,last=0;
            if(gtk_editable_get_selection_bounds(GTK_EDITABLE(focus),&first,&last) && last==int(text.size()))
                text=text.substr(0,first);
            if(text.empty() || text[0]!='/') return false;
            typed_path=text.raw();
            dialog.response(1001);
            return true;
        },false);
        auto response=dialog.run();
        if(response==1001) open_vault(typed_path);
        else if(response==Gtk::RESPONSE_OK) open_vault(dialog.get_filename());
    }
    void new_vault() {
        Gtk::Dialog dialog("New Vault",*this,true);
        Gtk::Entry entry; entry.set_activates_default(true);
        dialog.get_content_area()->pack_start(entry); dialog.add_button("_Cancel",Gtk::RESPONSE_CANCEL);
        dialog.add_button("_Create",Gtk::RESPONSE_OK); dialog.set_default_response(Gtk::RESPONSE_OK);
        dialog.show_all_children(); entry.grab_focus();
        if(dialog.run()!=Gtk::RESPONSE_OK) return;
        fs::path path(entry.get_text().raw());
        try {
            if(path.empty() || !path.is_absolute() || path==path.root_path() || path.filename().empty())
                throw std::runtime_error("Path must be an absolute new folder path");
            struct stat st{};
            if(lstat(path.c_str(),&st)==0 || errno!=ENOENT) throw std::runtime_error("Destination already exists or cannot be inspected");
            auto parent=fs::canonical(path.parent_path());
            if(stat(parent.c_str(),&st)!=0 || !S_ISDIR(st.st_mode) || !(st.st_mode&0222) || !(st.st_mode&0111) || access(parent.c_str(),W_OK|X_OK)!=0)
                throw std::runtime_error("Parent is not writable or traversable");
            if(!save()) { vault_error("Could not create vault: the current note was not saved."); return; }
            auto target=parent/path.filename();
            if(!fs::create_directory(target)) throw std::runtime_error("Destination already exists");
            try { install_vault(prepare_vault(target)); }
            catch(const std::exception& e) { throw std::runtime_error(std::string("Created empty folder but could not open it: ")+e.what()); }
        } catch(const std::exception& e) { vault_error(std::string("Cannot create vault: ")+e.what()); }
    }
    void recent_dialog() {
        Gtk::Dialog dialog("Recent Vaults",*this,true);
        Gtk::ScrolledWindow scroll; Gtk::TreeView list;
        auto model=Gtk::ListStore::create(columns); list.set_model(model); list.append_column("Vault",columns.label);
        for(const auto& path:recent_vaults()) { auto row=model->append(); (*row)[columns.label]=path; }
        scroll.add(list); scroll.set_min_content_width(500); scroll.set_min_content_height(200);
        dialog.get_content_area()->pack_start(scroll); dialog.add_button("_Cancel",Gtk::RESPONSE_CANCEL);
        dialog.add_button("_Open",Gtk::RESPONSE_OK); dialog.set_default_response(Gtk::RESPONSE_OK);
        list.signal_row_activated().connect([&](const Gtk::TreeModel::Path&,Gtk::TreeViewColumn*){dialog.response(Gtk::RESPONSE_OK);});
        dialog.show_all_children(); if(!model->children().empty()) list.set_cursor(Gtk::TreeModel::Path("0")); list.grab_focus();
        if(dialog.run()==Gtk::RESPONSE_OK) { auto row=list.get_selection()->get_selected(); if(row) open_vault(Glib::ustring((*row)[columns.label]).raw()); }
    }
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
    void refresh_outline() {
        outline_store->clear();
        if(document.path.empty()) return;
        try { for(const auto& h:headings(value())) {
            auto row=outline_store->append();
            (*row)[columns.label]=std::string((h.level-1)*2,' ')+h.text;
            (*row)[columns.line]=h.line;
        }} catch(const std::exception&) {}
    }
    void activate_outline() {
        auto row=outline_tree.get_selection()->get_selected();
        if(row) jump((*row)[columns.line],1);
    }
    void relocate_note(bool archive) {
        if(document.path.empty()) return;
        std::string folder;
        if(archive) {
            if(document.path.compare(0,8,"Archive/")==0) {message("Archive refused: already archived");return;}
            folder="Archive";
        } else {
            Gtk::Dialog dialog("Move Note",*this,true);Gtk::Entry entry;
            dialog.get_content_area()->pack_start(entry);dialog.add_button("_Cancel",Gtk::RESPONSE_CANCEL);
            dialog.add_button("_Move",Gtk::RESPONSE_OK);dialog.set_default_response(Gtk::RESPONSE_OK);
            entry.set_activates_default(true);dialog.show_all();entry.grab_focus();
            if(dialog.run()!=Gtk::RESPONSE_OK) return;
            folder=entry.get_text().raw();
        }
        auto prefix=archive?std::string("Archive/"):(folder.empty()?std::string{}:folder+"/");
        auto target=prefix+(archive?document.path:fs::path(document.path).filename().string());
        auto label=archive?"Archive refused: ":"Move refused: ";
        if(!save(label)) return;
        try {
            auto old=document.path;int offset=buffer->get_iter_at_mark(buffer->get_insert()).get_offset();
            auto result=vault.rename(old,target);offset=result.map_caret(offset);
            own_changes({old,result.to});document=Document{};refresh_tree();
            if(open_note(result.to)) {auto at=buffer->get_iter_at_offset(std::min(offset,buffer->get_char_count()));buffer->place_cursor(at);if(reading) place_reading_caret();}
        } catch(const std::exception& e) {message(std::string(label)+e.what());}
    }
    void supersede_dialog() {
        if(document.path.empty()) return;
        Gtk::Dialog dialog("Supersede With",*this,true);Gtk::Entry entry;
        dialog.get_content_area()->pack_start(entry);dialog.add_button("_Cancel",Gtk::RESPONSE_CANCEL);
        dialog.add_button("_Supersede",Gtk::RESPONSE_OK);dialog.set_default_response(Gtk::RESPONSE_OK);
        entry.set_activates_default(true);dialog.show_all();entry.grab_focus();
        if(dialog.run()!=Gtk::RESPONSE_OK) return;
        if(!save("Supersede refused: ")) return;
        try {auto path=document.path;supersede(vault,path,entry.get_text().raw());own_changes({path,entry.get_text().raw()});reload_disk();}
        catch(const SupersedePartialSave& e) {
            // OLD's permitted first write belongs to this operation. Update both
            // monitor and Document stamps before presenting the durable refusal.
            own_changes({document.path});reload_disk();
            message(std::string("Supersede refused: ")+e.what());
        }
        catch(const std::exception& e) {message(std::string("Supersede refused: ")+e.what());}
    }
    void refresh_properties() {
        for(auto child:properties_box.get_children()) properties_box.remove(*child);
        if(document.path.empty()) return;
        auto props=properties(value());
        auto add_link=[&](Gtk::Box& box,const std::string& label,std::function<void()> action) {
            auto button=Gtk::manage(new Gtk::LinkButton("about:blank",label));
            button->set_halign(Gtk::ALIGN_START);
            if(auto label_widget=dynamic_cast<Gtk::Label*>(button->get_child()))
                label_widget->set_markup("<span foreground=\"#205ca8\" underline=\"single\">"+Glib::Markup::escape_text(label)+"</span>");
            button->signal_activate_link().connect([action]{action();return true;},false);
            box.pack_start(*button,Gtk::PACK_SHRINK);
        };
        for(const auto& p:props) if(p.key=="superseded_by"&&!p.unsupported) {
            auto values=p.list?p.values:std::vector<std::string>{p.scalar};
            for(const auto& v:values) for(const auto& l:parse(v)) {
                auto target=vault.resolve(document.path,l.target);
                if(target&&is_note(*target)) add_link(properties_box,"Superseded by "+l.target,[this,target,l]{open_note(*target,l.heading);});
            }
        }
        if(!props.empty()) {
            auto heading=Gtk::manage(new Gtk::Label("Properties"));heading->set_halign(Gtk::ALIGN_START);properties_box.pack_start(*heading,Gtk::PACK_SHRINK);
            for(const auto& p:props) {
                auto row=Gtk::manage(new Gtk::Box(Gtk::ORIENTATION_HORIZONTAL));
                auto key=Gtk::manage(new Gtk::Label(p.key+": "));row->pack_start(*key,Gtk::PACK_SHRINK);
                auto values=p.list?p.values:std::vector<std::string>{p.scalar};
                bool action=!p.unsupported&&(p.key=="tags"||p.key=="tag"||p.key=="alias"||p.key=="aliases");
                if(action&&!p.list&&(p.key=="tags"||p.key=="tag")) {
                    values=scalar_property_tags(value(),p);
                    if(values.empty()) {values={p.scalar};action=false;}
                }
                bool first_value=true;
                if(action) for(const auto& v:values) {
                    if(!first_value) {auto separator=Gtk::manage(new Gtk::Label(", "));row->pack_start(*separator,Gtk::PACK_SHRINK);}
                    first_value=false;
                    if(p.key=="tag"||p.key=="tags") add_link(*row,v,[this,v]{
                        auto tag=v;if(!tag.empty()&&tag[0]=='#')tag.erase(0,1);
                        sidebar.set_current_page(1);
                        for(auto r=tag_store->children().begin();r!=tag_store->children().end();++r) if(fold(Glib::ustring((*r)[columns.text]).raw())==fold(tag)) {
                            auto path=tag_store->get_path(r);tags_tree.expand_row(path,false);
                            if(!r->children().empty()) tags_tree.set_cursor(tag_store->get_path(r->children().begin()));
                            tags_tree.grab_focus();break;
                        }
                    });
                    else add_link(*row,v,[this,v]{auto target=vault.resolve(document.path,v);if(target&&is_note(*target)) open_note(*target);});
                } else {
                    std::string text;for(const auto& v:values) {if(!text.empty())text+=", ";text+=v;}
                    auto label=Gtk::manage(new Gtk::Label(text));label->set_halign(Gtk::ALIGN_START);row->pack_start(*label,Gtk::PACK_SHRINK);
                }
                properties_box.pack_start(*row,Gtk::PACK_SHRINK);
            }
        }
        properties_box.show_all();
    }
    void refresh_reading() {
        refresh_properties();
        rendered=document.path.empty()?Render{}:vault.render(document.path,value());
        reading_images.clear();
        reading_buffer->set_text(rendered.text);
        for(auto& image:rendered.images) {
            auto at=reading_buffer->get_iter_at_offset(image.offset), end=reading_buffer->get_iter_at_offset(image.offset+1);
            reading_buffer->erase(at,end);at=reading_buffer->get_iter_at_offset(image.offset);
            try {
                auto pix=Gdk::Pixbuf::create_from_file((vault.root/image.path).string());
                auto anchor=reading_buffer->create_child_anchor(at);
                auto widget=Gtk::manage(new Gtk::Image());
                reading_view.add_child_at_anchor(*widget,anchor);widget->show();
                int margin=extra_margin(image.offset);
                reading_images.push_back({widget,pix,margin,image.offset});
            } catch(const Glib::Error&) {
                auto anchor=reading_buffer->create_child_anchor(at);
                auto label=Gtk::manage(new Gtk::Label("[image: "+image.path+"]"));
                label->override_color(Gdk::RGBA("#a33b24"));reading_view.add_child_at_anchor(*label,anchor);label->show();
            }
        }
        resize_reading_images();
        fold_closed.clear();
        std::set<int> boundaries{0,reading_buffer->get_char_count()};
        std::set<int> callout_boundaries;
        std::map<const decltype(rendered.spans)::value_type*,int> callout_starts;
        for(auto& s:rendered.spans) {
            if(s.style=="folded") {fold_closed.push_back(true);continue;}
            if(s.style.compare(0,8,"callout-")==0 && s.style!="callout-title") {
                // Callouts are blocks. GTK reads paragraph backgrounds at the
                // paragraph start, including any recursively generated list prefix.
                // Expand only the paint range; semantic text/link/fold ranges stay put.
                auto at=reading_buffer->get_iter_at_offset(s.start), line=at;
                line.set_line_offset(0);
                int start=line.get_offset();
                callout_starts[&s]=start;
                callout_boundaries.insert(start);callout_boundaries.insert(s.end);continue;
            }
            reading_buffer->apply_tag(reading_tags.at(s.style),reading_buffer->get_iter_at_offset(s.start),reading_buffer->get_iter_at_offset(s.end));
        }
        // Apply only the innermost callout on each interval. GTK tag priority
        // is global, so overlapping kind tags cannot express nesting order.
        for(auto it=callout_boundaries.begin();it!=callout_boundaries.end();) {
            int start=*it++;if(it==callout_boundaries.end()) break;
            int end=*it;const decltype(rendered.spans)::value_type* inner=nullptr;
            for(const auto& s:rendered.spans)
                if(s.style.compare(0,8,"callout-")==0 && s.style!="callout-title" &&
                   callout_starts.at(&s)<=start && end<=s.end &&
                   (!inner || s.end-s.start<inner->end-inner->start)) inner=&s;
            if(inner) reading_buffer->apply_tag(reading_tags.at(inner->style),
                reading_buffer->get_iter_at_offset(start),reading_buffer->get_iter_at_offset(end));
        }
        for(const auto& s:rendered.layout_spans) {boundaries.insert(s.start);boundaries.insert(s.end);}
        // GTK margins are paragraph properties. Include the list prefix when
        // an embedded range begins after it, and restore the next line's margin.
        for(int line=0;line<reading_buffer->get_line_count();++line) {
            auto begin=reading_buffer->get_iter_at_line(line),end=begin;
            if(!end.forward_line()) end=reading_buffer->end();
            int first=begin.get_offset(),last=end.get_offset();
            int margin=extra_margin(first);
            for(auto it=boundaries.upper_bound(first);it!=boundaries.end()&&*it<last;++it)
                margin=std::max(margin,extra_margin(*it));
            if(!margin) continue;
            if(!margin_tags.count(margin)) {
                auto tag=reading_buffer->create_tag();tag->property_left_margin()=12+margin;
                margin_tags[margin]=tag;
            }
            reading_buffer->apply_tag(margin_tags.at(margin),begin,end);
        }
        update_folds();
        Glib::signal_idle().connect_once([this]{resize_reading_images();});
        place_reading_caret();
    }
    void resize_reading_images() {
        int allocated=reading_view.get_allocated_width();
        if(allocated<=1) allocated=editor.get_allocated_width();
        for(auto& image:reading_images) {
            auto pix=image.pixbuf;
            Gdk::Rectangle rect;
            auto at=reading_buffer->get_iter_at_offset(image.offset),line_start=at;
            line_start.set_line_offset(0);
            auto prefix=reading_view.create_pango_layout(reading_buffer->get_text(line_start,at));
            int prefix_width=0,prefix_height=0;prefix->get_pixel_size(prefix_width,prefix_height);
            reading_view.get_iter_location(at,rect);
            int actual_left=std::max(reading_view.get_left_margin()+image.extra_margin+prefix_width,rect.get_x());
            // Leave a few pixels for GTK/Pango rounding after an inline list marker.
            int target=std::min(std::max(1,allocated-reading_view.get_right_margin()-actual_left-(prefix_width?4:0)),pix->get_width());
            auto current=image.widget->get_pixbuf();
            if(current&&current->get_width()==target) continue;
            if(target<pix->get_width()) pix=pix->scale_simple(target,std::max(1,pix->get_height()*target/pix->get_width()),Gdk::INTERP_BILINEAR);
            image.widget->set(pix);
        }
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
        if(reading_item) reading_item->set_active(reading);
        views.set_visible_child(reading?"reading":"editor");
        if(reading) refresh_reading();
        focus_content();position();
    }
    void follow_reading(int offset) {
        for(auto& l:rendered.links) if(l.start<=offset&&offset<l.end) {
            auto parsed=parse_all(l.raw);if(parsed.empty()) return;auto link=parsed.front();
            try {
                if(l.resolved&&!is_note(*l.resolved)) {message("Not a note: "+*l.resolved);return;}
                if(!save()) return;
                auto path=l.resolved;
                if(!path) {open_created(vault.create(creation_target(l.source,link)),link.heading);return;}
                open_note(*path,link.heading);
            } catch(const std::exception& e) {message(std::string("refused: ")+e.what());}
            return;
        }
    }
    void follow_current() {
        if(reading) follow_reading(reading_buffer->get_iter_at_mark(reading_buffer->get_insert()).get_offset());
        else follow(buffer->get_iter_at_mark(buffer->get_insert()).get_offset());
    }
    bool save(const std::string& refusal_prefix={}) {
        if(document.path.empty()) return true;
        try {
            bool wrote=dirty(),restoring=document.deleted();document.save(vault,value());
            if(wrote) own_changes();
            if(restoring) refresh_tree(true);
            refresh_u2();update_title();position();return true;
        }
        catch(const std::exception& e) {message(refusal_prefix+e.what());return false;}
    }
    void refresh_tree(bool preserve=false) {
        std::set<std::string> expanded;std::string selected;
        auto selection=tree.get_selection()->get_selected();if(selection) selected=Glib::ustring((*selection)[columns.path]).raw();
        std::function<void(const Gtk::TreeModel::Children&)> capture=[&](const Gtk::TreeModel::Children& children) {
            for(auto row=children.begin();row!=children.end();++row) {
                if(tree.row_expanded(store->get_path(row))) expanded.insert(Glib::ustring((*row)[columns.path]).raw());
                capture(row->children());
            }
        };if(preserve) capture(store->children());
        store->clear(); std::map<std::string,Gtk::TreeModel::iterator> folders;
        for(auto& path:vault.directories()) {
            auto parent=folders.find(fs::path(path).parent_path().generic_string());
            auto row=parent==folders.end()?store->append():store->append(parent->second->children());
            (*row)[columns.label]=fs::path(path).filename().string(); (*row)[columns.path]=path;
            folders[path]=row;
        }
        auto files=vault.files();
        std::stable_sort(files.begin(),files.end(),[](auto& a,auto& b){return is_note(a)>is_note(b);});
        for(auto& path:files) {
            auto parent=folders.find(fs::path(path).parent_path().generic_string());
            auto row=parent==folders.end()?store->append():store->append(parent->second->children());
            (*row)[columns.label]=fs::path(path).filename().string(); (*row)[columns.path]=path;
        }
        if(!preserve) {tree.expand_all();select_note();}
        else {
            std::function<void(const Gtk::TreeModel::Children&)> restore=[&](const Gtk::TreeModel::Children& children) {
                for(auto row=children.begin();row!=children.end();++row) {
                    auto path=Glib::ustring((*row)[columns.path]).raw();auto index=store->get_path(row);
                    if(expanded.count(path)) tree.expand_row(index,false);
                    if(path==selected) tree.set_cursor(index);
                    restore(row->children());
                }
            };restore(store->children());
        }
    }
    void select_note() {
        std::function<bool(const Gtk::TreeModel::Children&)> visit;
        visit=[&](const Gtk::TreeModel::Children& children) {
            for(auto row=children.begin();row!=children.end();++row) {
                if(Glib::ustring((*row)[columns.path]).raw()==document.path&&!document.path.empty()) {
                    auto path=store->get_path(row);tree.expand_to_path(path);
                    tree.set_cursor(path);tree.scroll_to_row(path);return true;
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
        try {for(auto& l:vault.all_links(document.path,value())) {
            buffer->apply_tag(l.resolved?resolved_tag:unresolved_tag,buffer->get_iter_at_offset(l.offset),buffer->get_iter_at_offset(l.offset+l.length));
        }} catch(const std::exception& e) {message(e.what());}
    }
    void refresh_u2(const Rename* tag_rename=nullptr,bool preserve_tree=false) {
        if(!preserve_tree) select_note();
        // Saved row identities are folded already, so prefix lengths remain
        // correct even when Unicode folding expands the displayed spelling.
        auto identity=[&](const Glib::ustring& tag) {
            auto key=fold(tag.raw());
            if(tag_rename) {
                auto old=fold(tag_rename->from);
                if(key==old||key.compare(0,old.size()+1,old+"/")==0)
                    key=fold(tag_rename->to)+key.substr(old.size());
            }
            return key;
        };
        std::set<std::string> expanded;
        std::string selected_tag,selected_note;
        std::optional<Gtk::TreeModel::Path> selected_path;
        auto selection=tags_tree.get_selection()->get_selected();
        const bool had_selection=bool(selection);
        if(selection) {
            selected_tag=identity((*selection)[columns.text]);
            selected_note=Glib::ustring((*selection)[columns.path]).raw();
        }
        for(auto row=tag_store->children().begin();row!=tag_store->children().end();++row)
            if(tags_tree.row_expanded(tag_store->get_path(row))) expanded.insert(identity((*row)[columns.text]));
        tag_store->clear();backlink_store->clear();mention_store->clear();
        try {
            for(auto& t:vault.tags()) {
                auto row=tag_store->append();(*row)[columns.label]=t.tag+" ("+std::to_string(t.count)+")";(*row)[columns.text]=t.tag;
                for(auto& path:t.notes) {
                    auto child=tag_store->append(row->children());(*child)[columns.label]=path;(*child)[columns.path]=path;(*child)[columns.text]=t.tag;
                    if(had_selection&&fold(t.tag)==selected_tag&&path==selected_note) selected_path=tag_store->get_path(child);
                }
                if(expanded.count(fold(t.tag))) tags_tree.expand_row(tag_store->get_path(row),false);
                if(had_selection&&fold(t.tag)==selected_tag&&selected_note.empty()) selected_path=tag_store->get_path(row);
            }
            // Child cursors can only be restored once their parents are expanded.
            if(selected_path) tags_tree.set_cursor(*selected_path);
        } catch(const std::exception& e) {message(e.what());}
        try {
            if(!document.path.empty()) for(auto& m:vault.mentions(document.path)) {
                auto row=mention_store->append();(*row)[columns.label]=m.source+" (line "+std::to_string(m.line)+")";(*row)[columns.text]=m.text;
                (*row)[columns.path]=m.source;(*row)[columns.line]=m.line;(*row)[columns.col]=m.col;
            }
        } catch(const std::exception& e) {message(e.what());}
        try {
            if(!document.path.empty()) for(auto& b:vault.backlinks(document.path)) {
                auto row=backlink_store->append();(*row)[columns.label]=b.source+" (line "+std::to_string(b.line)+")";(*row)[columns.text]=b.text;
                (*row)[columns.path]=b.source;(*row)[columns.line]=b.line;(*row)[columns.col]=b.col;
            }
        } catch(const std::exception& e) {message(e.what());}
        style_links();refresh_outline();
    }
    void jump(int line,int col) {
        auto at=buffer->get_iter_at_line(line-1);at.forward_chars(col-1);
        buffer->place_cursor(at);editor.scroll_to(at,0.1);if(reading) place_reading_caret();focus_content();position();
    }
    void open_backlink(bool mention=false) {
        auto row=(mention?mentions_tree:backlinks_tree).get_selection()->get_selected();if(!row) return;
        auto path=Glib::ustring((*row)[columns.path]).raw();int line=(*row)[columns.line],col=(*row)[columns.col];
        if(open_note(path)) jump(line,col);
    }
    void search_dialog() {
        Gtk::Dialog dialog("Search",*this,true);dialog.set_default_size(640,360);
        Gtk::Entry entry;Gtk::ScrolledWindow scroll;Gtk::TreeView results;
        Gtk::CheckButton regex{"_Regular expression",true},word{"_Whole word",true};
        Gtk::Label feedback;
        dialog.get_content_area()->pack_start(regex,Gtk::PACK_SHRINK);
        dialog.get_content_area()->pack_start(word,Gtk::PACK_SHRINK);
        auto matches=Gtk::ListStore::create(columns);
        results.set_model(matches);results.append_column("Matches",columns.label);results.set_headers_visible(false);
        scroll.add(results);scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        dialog.get_content_area()->pack_start(entry,Gtk::PACK_SHRINK);dialog.get_content_area()->pack_start(scroll);dialog.get_content_area()->pack_end(feedback,Gtk::PACK_SHRINK);
        auto update=[&]() {
            matches->clear();feedback.set_text("");
            try {if(!entry.get_text().empty()) for(auto& m:vault.find(entry.get_text().raw(),regex.get_active(),word.get_active())) {
                auto row=matches->append();(*row)[columns.label]=m.path+":"+std::to_string(m.line)+": "+m.text;
                (*row)[columns.path]=m.path;(*row)[columns.line]=m.line;(*row)[columns.col]=m.col;
            }} catch(const std::exception&) {feedback.set_text("Invalid expression");}
            if(!matches->children().empty()) results.get_selection()->select(matches->children().begin());
        };
        regex.signal_toggled().connect(update);word.signal_toggled().connect(update);
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
    void rename_dialog(bool selected=false) {
        std::string old=document.path;
        bool tag=false;
        if(selected&&tree.has_focus()) {
            auto row=tree.get_selection()->get_selected();if(!row) return;
            old=Glib::ustring((*row)[columns.path]).raw();
        } else if(selected&&tags_tree.has_focus()) {
            auto row=tags_tree.get_selection()->get_selected();if(!row) return;
            if(!Glib::ustring((*row)[columns.path]).empty()) return;
            old=Glib::ustring((*row)[columns.text]).raw();tag=true;
        }
        if(old.empty()) return;
        Gtk::Dialog dialog(tag?"Rename Tag":"Rename",*this,true);Gtk::Entry entry;
        entry.set_text(!tag&&is_note(old)?old.substr(0,old.size()-3):old);entry.select_region(0,-1);
        dialog.get_content_area()->pack_start(entry);dialog.set_default_size(440,120);
        dialog.add_button("_Cancel",Gtk::RESPONSE_CANCEL);dialog.add_button("_Rename",Gtk::RESPONSE_OK);dialog.set_default_response(Gtk::RESPONSE_OK);
        entry.set_activates_default(true);
        dialog.signal_key_press_event().connect([&](GdkEventKey* event) {
            if(event->keyval==GDK_KEY_Escape) {dialog.response(Gtk::RESPONSE_CANCEL);return true;}return false;
        },false);
        dialog.show_all();entry.grab_focus();auto response=dialog.run();dialog.hide();
        if(response==Gtk::RESPONSE_OK) {
            int offset=buffer->get_iter_at_mark(buffer->get_insert()).get_offset();
            auto current=document.path;
            try {
                bool wrote=dirty();document.save(vault,value());if(wrote) own_changes();update_title();
                auto result=tag?vault.retag(old,entry.get_text().raw()):vault.rename(old,entry.get_text().raw());
                std::vector<std::string> affected=result.updated;
                if(!tag) {
                    affected.push_back(old);affected.push_back(result.to);
                    for(auto& entry:disk_state) if(entry.first.compare(0,old.size()+1,old+"/")==0) {
                        affected.push_back(entry.first);affected.push_back(result.to+entry.first.substr(old.size()));
                    }
                }
                own_changes(affected);
                if(result.note_rewrites.count(current)) {
                    Rename mapping;mapping.rewrites=result.note_rewrites.at(current);offset=mapping.map_caret(offset);
                }
                if(!tag&&(current==old||current.compare(0,old.size()+1,old+"/")==0)) current=result.to+current.substr(old.size());
                document=Document{};refresh_tree();
                // Rebase tag state before open_note's save/refresh can discard
                // the old identities. Subsequent refreshes keep the new ones.
                if(tag) refresh_u2(&result);
                if(!current.empty()&&open_note(current)) {
                    auto at=buffer->get_iter_at_offset(std::min(offset,buffer->get_char_count()));
                    buffer->place_cursor(at);editor.scroll_to(at,0.1);if(reading) place_reading_caret();position();
                } else refresh_u2();
            } catch(const std::exception& e) {refresh_u2();message(std::string("Rename refused: ")+e.what());}
        }
        focus_content();
    }
    void open_created(const std::pair<std::string,bool>& created,const Maybe& heading={}) {
        if(created.second) own_changes({created.first});
        if(created.second&&reading) toggle_reading();
        refresh_tree();
        if(open_note(created.first,heading)&&created.second) {
            buffer->place_cursor(buffer->end());editor.grab_focus();position();
        }
    }
    void today_note() {
        if(!save()) return;
        try {auto d=daily(vault,clock_now(false),"today",true);if(d.created) own_changes({d.path});if(reading) toggle_reading();refresh_tree();if(open_note(d.path)){buffer->place_cursor(buffer->end());editor.grab_focus();position();}}
        catch(const std::exception& e){message(std::string("refused: ")+e.what());}
    }
    void adjacent_daily(bool next) {
        try {auto days=dailies(vault,clock_now(false));auto it=std::find_if(days.begin(),days.end(),[this](const Daily& d){return d.path==document.path;});if(it==days.end()){message("Not a daily note");return;}auto current_date=it->date;if(next){do{++it;}while(it!=days.end()&&it->date==current_date);if(it==days.end()){message("No later daily note");return;}}else {while(it!=days.begin()&&it->date==current_date)--it;if(it->date==current_date){message("No earlier daily note");return;}}open_note(it->path);}
        catch(const std::exception& e){message(std::string("refused: ")+e.what());}
    }
    std::string template_display(const std::string& path,const std::string& folder) {
        size_t at=0;for(size_t i=0;i<=std::count(folder.begin(),folder.end(),'/');++i){at=path.find('/',at);if(at==std::string::npos)return path;++at;}return path.substr(at,path.size()-at-3);
    }
    void insert_template() {
        if(reading||document.path.empty())return;
        auto paths=templates(vault);if(paths.empty()){message("No templates in "+template_folder(vault));return;}
        Gtk::Dialog dialog("Insert Template",*this,true);Gtk::ListBox list;list.set_selection_mode(Gtk::SELECTION_SINGLE);list.set_activate_on_single_click(false);auto folder=template_folder(vault);for(auto& p:paths){auto label=Gtk::manage(new Gtk::Label(template_display(p,folder)));label->set_halign(Gtk::ALIGN_START);list.append(*label);}dialog.get_content_area()->pack_start(list);dialog.add_button("_Cancel",Gtk::RESPONSE_CANCEL);dialog.add_button("_Insert",Gtk::RESPONSE_OK);dialog.set_default_response(Gtk::RESPONSE_OK);list.signal_row_activated().connect([&](Gtk::ListBoxRow*){dialog.response(Gtk::RESPONSE_OK);});dialog.show_all();list.select_row(*list.get_row_at_index(0));list.grab_focus();auto response=dialog.run();auto row=list.get_selected_row();int index=row?row->get_index():-1;dialog.hide();if(response==Gtk::RESPONSE_OK&&index>=0)try{auto text=template_text(vault,paths.at(index),fs::path(document.path).stem().string(),clock_now(false));buffer->begin_user_action();buffer->erase_selection(true,true);buffer->insert_at_cursor(text);buffer->end_user_action();editor.grab_focus();}catch(const std::exception& e){message(std::string("refused: ")+e.what());}
    }
    void new_note() {
        Gtk::Dialog dialog("New Note",*this,true);
        Gtk::Label hint{"Name or path, for example Projects/Idea"};Gtk::Entry entry;
        hint.set_alignment(0.0, 0.5);
        dialog.get_content_area()->pack_start(hint);dialog.get_content_area()->pack_start(entry);
        Gtk::Label template_label("_Template:",true);template_label.set_alignment(0.0, 0.5);Gtk::ComboBoxText choices;auto paths=templates(vault);choices.append("None");auto folder=template_folder(vault);for(auto& p:paths)choices.append(template_display(p,folder));choices.set_active(0);template_label.set_mnemonic_widget(choices);choices.signal_key_press_event().connect([&](GdkEventKey* e){if(choices.property_popup_shown().get_value())return false;if(e->keyval==GDK_KEY_Down||e->keyval==GDK_KEY_Up){int n=choices.get_active_row_number()+(e->keyval==GDK_KEY_Down?1:-1);choices.set_active(std::max(0,std::min(n,static_cast<int>(paths.size()))));return true;}if(e->keyval==GDK_KEY_Return||e->keyval==GDK_KEY_KP_Enter){dialog.response(Gtk::RESPONSE_OK);return true;}return false;},false);dialog.get_content_area()->pack_start(template_label);dialog.get_content_area()->pack_start(choices);
        Gtk::Button timestamp("Timestamp _Name",true);dialog.get_content_area()->pack_start(timestamp);timestamp.signal_clicked().connect([&]{try{entry.set_text(unique_target(vault,clock_now(false)));entry.grab_focus();entry.set_position(-1);entry.select_region(-1,-1);}catch(const std::exception& e){message(std::string("refused: ")+e.what());}});
        dialog.add_button("_Cancel",Gtk::RESPONSE_CANCEL);dialog.add_button("_Create",Gtk::RESPONSE_OK);
        dialog.set_default_response(Gtk::RESPONSE_OK);entry.set_activates_default(true);
        dialog.signal_key_press_event().connect([&](GdkEventKey* e) {
            if(e->keyval==GDK_KEY_Escape) {dialog.response(Gtk::RESPONSE_CANCEL);return true;}
            if((e->state&GDK_MOD1_MASK)&&(e->keyval==GDK_KEY_n||e->keyval==GDK_KEY_N)){timestamp.clicked();return true;}
            if(!choices.property_popup_shown().get_value()&&(e->keyval==GDK_KEY_Return||e->keyval==GDK_KEY_KP_Enter)){dialog.response(Gtk::RESPONSE_OK);return true;}
            return false;
        },false);
        dialog.show_all();entry.grab_focus();auto response=dialog.run();dialog.hide();
        if(response==Gtk::RESPONSE_OK&&save()) {
            try {auto i=choices.get_active_row_number();open_created(i>0?create_template(vault,entry.get_text().raw(),paths.at(i-1),clock_now(false)):vault.create(entry.get_text().raw()));}
            catch(const std::exception& e) {message(std::string("refused: ")+e.what());}
        }
        focus_content();
    }
    void focus_sidebar(bool tags) {
        sidebar.set_current_page(tags?1:0);
        auto& view=tags?tags_tree:tree;
        auto model=tags?tag_store:store;
        if(!tags) select_note();
        if((tags||document.path.empty()||!view.get_selection()->get_selected())&&!model->children().empty()) view.set_cursor(model->get_path(model->children().begin()));
        view.grab_focus();
    }
    void focus_backlinks(bool mentions=false) {
        auto& view=mentions?mentions_tree:backlinks_tree;auto model=mentions?mention_store:backlink_store;
        if(!model->children().empty()) view.set_cursor(model->get_path(model->children().begin()));
        view.grab_focus();
    }
    void activate_tree() {
        auto row=tree.get_selection()->get_selected();if(!row) return;
        auto path=Glib::ustring((*row)[columns.path]).raw();
        if(is_note(path)) open_note(path);
        else if(fs::is_directory(vault.root/path)) {
            auto p=store->get_path(row);if(tree.row_expanded(p)) tree.collapse_row(p);else tree.expand_row(p,false);
        } else message("Not a note: "+path);
    }
    void activate_tag() {
        auto row=tags_tree.get_selection()->get_selected();if(!row) return;
        auto note=Glib::ustring((*row)[columns.path]).raw();
        if(!note.empty()) open_note(note);
        else {auto p=tag_store->get_path(row);if(tags_tree.row_expanded(p)) tags_tree.collapse_row(p);else tags_tree.expand_row(p,false);}
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
            for(auto& l:vault.all_links(document.path,value())) {
                if(offset<l.offset || (!clicked && offset==l.offset) || offset>=l.offset+l.length) continue;
                if(l.resolved && !is_note(*l.resolved)) {message("Not a note: "+*l.resolved);return;}
                if(!save()) return;
                auto path=l.resolved;
                if(!path) {open_created(vault.create(creation_target(document.path,l)),l.heading);return;}
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
        Gtk::Label hint{"Open a note by name or path. Ctrl+Shift+F searches note contents."};
        auto box=dialog.get_content_area();box->pack_start(hint,Gtk::PACK_SHRINK);box->pack_start(entry,Gtk::PACK_SHRINK);box->pack_start(scroll);
        auto update=[&]() {
            matches->clear();
            std::map<std::string,std::string> matched_aliases;
            try {for(auto& path:vault.search(entry.get_text().raw(),&matched_aliases)) {
                auto row=matches->append();(*row)[columns.label]=matched_aliases.count(path)?matched_aliases.at(path)+" → "+path:path;(*row)[columns.path]=path;
            }} catch(const std::exception& e) {message(e.what());}
            auto query=entry.get_text().raw();auto resolved=vault.resolve("",trim(query));
            if(!query.empty()&&(!resolved||!is_note(*resolved))) {
                auto row=matches->append();(*row)[columns.label]="Create \""+query+"\"";(*row)[columns.path]="";
            }
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
                if(row&&!Glib::ustring((*row)[columns.path]).empty()) open_note(Glib::ustring((*row)[columns.path]).raw());
                else if(save()) open_created(vault.create(entry.get_text().raw()));
            } catch(const std::exception& e) {message(std::string("refused: ")+e.what());}
        }
        focus_content();
    }
    bool sidebar_arrow(Gtk::TreeView& view,const Glib::RefPtr<Gtk::TreeStore>& model,guint keyval) {
        auto row=view.get_selection()->get_selected();if(!row) return true;
        auto path=model->get_path(row);
        if(keyval==GDK_KEY_Right) {
            if(!view.row_expanded(path)) view.expand_row(path,false);
            else if(!row->children().empty()) view.set_cursor(model->get_path(row->children().begin()));
        } else if(keyval==GDK_KEY_Left) {
            if(view.row_expanded(path)) view.collapse_row(path);
            else if(path.up()) view.set_cursor(path);
        } else {
            std::vector<Gtk::TreeModel::Path> visible;
            std::function<void(const Gtk::TreeModel::Children&)> visit=[&](const Gtk::TreeModel::Children& children) {
                for(auto it=children.begin();it!=children.end();++it) {
                    auto p=model->get_path(it);visible.push_back(p);
                    if(view.row_expanded(p)) visit(it->children());
                }
            };
            visit(model->children());
            auto it=std::find(visible.begin(),visible.end(),path);
            if(it!=visible.end()) {
                if(keyval==GDK_KEY_Down&&it+1!=visible.end()) ++it;
                else if(keyval==GDK_KEY_Up&&it!=visible.begin()) --it;
                view.set_cursor(*it);view.scroll_to_row(*it);
            }
        }
        return true;
    }
    void edit_highlight() {
        if(reading||document.path.empty()) return;
        Gtk::TextBuffer::iterator a,b;
        bool selected=buffer->get_selection_bounds(a,b);
        int start=selected?a.get_offset():buffer->get_iter_at_mark(buffer->get_insert()).get_offset();
        int end=selected?b.get_offset():start;
        Glib::ustring all=buffer->get_text();
        bool unwrap=selected&&start>=2&&end+2<=int(all.size())&&all.substr(start-2,2)=="=="&&all.substr(end,2)=="==";
        buffer->begin_user_action();
        if(unwrap) {
            buffer->erase(buffer->get_iter_at_offset(end),buffer->get_iter_at_offset(end+2));
            buffer->erase(buffer->get_iter_at_offset(start-2),buffer->get_iter_at_offset(start));
            start-=2;end-=2;
        } else {
            buffer->insert(buffer->get_iter_at_offset(end),"==");
            buffer->insert(buffer->get_iter_at_offset(start),"==");
            start+=2;end+=2;
        }
        if(selected) buffer->select_range(buffer->get_iter_at_offset(start),buffer->get_iter_at_offset(end));
        else buffer->place_cursor(buffer->get_iter_at_offset(start));
        buffer->end_user_action();
    }
    void highlights_dialog() {
        if(document.path.empty()) return;
        auto result=vault.render(document.path,value());
        Gtk::Dialog dialog("Highlights",*this,true);dialog.set_default_size(420,260);
        Gtk::ScrolledWindow scroll;Gtk::TreeView list;auto model=Gtk::ListStore::create(columns);
        list.set_model(model);list.append_column("Highlight",columns.label);list.set_headers_visible(false);
        Glib::ustring text=result.text;
        for(auto& span:result.spans) if(span.style=="highlight") {
            auto row=*model->append();row[columns.label]=text.substr(span.start,span.end-span.start);row[columns.line]=span.start;
        }
        if(!model->children().empty()) list.get_selection()->select(model->children().begin());
        else {auto label=Gtk::manage(new Gtk::Label("No highlights in this note"));dialog.get_content_area()->pack_start(*label,Gtk::PACK_SHRINK);}
        scroll.add(list);dialog.get_content_area()->pack_start(scroll);
        list.signal_row_activated().connect([&](const Gtk::TreeModel::Path&,Gtk::TreeViewColumn*){dialog.response(Gtk::RESPONSE_OK);});
        dialog.signal_key_press_event().connect([&](GdkEventKey* e) {
            if(e->keyval==GDK_KEY_Escape) {dialog.response(Gtk::RESPONSE_CANCEL);return true;}
            if(e->keyval==GDK_KEY_Return||e->keyval==GDK_KEY_KP_Enter) {dialog.response(Gtk::RESPONSE_OK);return true;}
            return false;
        },false);
        dialog.show_all();list.grab_focus();
        if(dialog.run()==Gtk::RESPONSE_OK) {
            auto row=list.get_selection()->get_selected();
            if(row) {int offset=(*row)[columns.line];if(!reading) toggle_reading();
                reading_buffer->place_cursor(reading_buffer->get_iter_at_offset(offset));reading_view.grab_focus();scroll_reading_caret();}
        }
    }
    bool key(GdkEventKey* event) {
        if(reading&&reading_view.has_focus()&&event->keyval==GDK_KEY_space&&!(event->state&(GDK_CONTROL_MASK|GDK_MOD1_MASK))) {
            toggle_task(reading_buffer->get_iter_at_mark(reading_buffer->get_insert()).get_offset());return true;
        }
        bool ctrl=event->state&GDK_CONTROL_MASK,alt=event->state&GDK_MOD1_MASK;
        bool shift=event->state&GDK_SHIFT_MASK;
        if(!ctrl&&!alt&&(event->keyval==GDK_KEY_Up||event->keyval==GDK_KEY_Down||event->keyval==GDK_KEY_Left||event->keyval==GDK_KEY_Right)) {
            if(tags_tree.has_focus()) return sidebar_arrow(tags_tree,tag_store,event->keyval);
            if(tree.has_focus()) return sidebar_arrow(tree,store,event->keyval);
        }
        if(ctrl&&shift&&(event->keyval==GDK_KEY_i||event->keyval==GDK_KEY_I)){insert_template();return true;}
        if(ctrl&&!shift&&!alt&&(event->keyval==GDK_KEY_d||event->keyval==GDK_KEY_D)) {today_note();return true;}
        if(alt&&!ctrl&&!shift&&(event->keyval==GDK_KEY_Left||event->keyval==GDK_KEY_Right)){adjacent_daily(event->keyval==GDK_KEY_Right);return true;}
        if(ctrl&&shift&&(event->keyval==GDK_KEY_y||event->keyval==GDK_KEY_Y)) {highlights_dialog();return true;}
        if(ctrl&&shift&&(event->keyval==GDK_KEY_h||event->keyval==GDK_KEY_H)) {edit_highlight();return true;}
        if(ctrl&&shift&&(event->keyval==GDK_KEY_r||event->keyval==GDK_KEY_R)) {reload_disk();return true;}
        if(event->keyval==GDK_KEY_F6) {relocate_note(false);return true;}
        if(ctrl&&shift&&(event->keyval==GDK_KEY_o||event->keyval==GDK_KEY_O)) {sidebar.set_current_page(2);if(!outline_store->children().empty()) outline_tree.set_cursor(outline_store->get_path(outline_store->children().begin()));outline_tree.grab_focus();return true;}
        if(event->keyval==GDK_KEY_F2) {rename_dialog(true);return true;}
        if(ctrl&&shift&&(event->keyval==GDK_KEY_e||event->keyval==GDK_KEY_E)) {focus_sidebar(false);return true;}
        if(ctrl&&shift&&(event->keyval==GDK_KEY_t||event->keyval==GDK_KEY_T)) {focus_sidebar(true);return true;}
        if(ctrl&&shift&&(event->keyval==GDK_KEY_m||event->keyval==GDK_KEY_M)) {focus_backlinks(true);return true;}
        if(ctrl&&(event->keyval==GDK_KEY_n||event->keyval==GDK_KEY_N)) {new_note();return true;}
        if(ctrl&&shift&&(event->keyval==GDK_KEY_f||event->keyval==GDK_KEY_F)) {search_dialog();return true;}
        if(ctrl&&shift&&(event->keyval==GDK_KEY_b||event->keyval==GDK_KEY_B)) {
            focus_backlinks();return true;
        }
        if(ctrl && (event->keyval==GDK_KEY_e || event->keyval==GDK_KEY_E)) {toggle_reading();return true;}
        if(reading && ctrl&&(event->keyval==GDK_KEY_z||event->keyval==GDK_KEY_Z||event->keyval==GDK_KEY_y||event->keyval==GDK_KEY_Y)) return true;
        bool enter=event->keyval==GDK_KEY_Return || event->keyval==GDK_KEY_KP_Enter;
        if(enter&&!alt&&!ctrl) {
            if(outline_tree.has_focus()) {activate_outline();return true;}
            if(tree.has_focus()) {activate_tree();return true;}
            if(tags_tree.has_focus()) {activate_tag();return true;}
            if(backlinks_tree.has_focus()) {open_backlink();return true;}
            if(mentions_tree.has_focus()) {open_backlink(true);return true;}
        }
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
    ~Window() override {notify_connection.disconnect();external_pending.disconnect();if(notify_fd>=0) ::close(notify_fd);}
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
                backlinks_split.set_position(std::max(150,(height-60)*2/3));
            },100);
            return false;
        });
        menu("_File",{{"_Open Vault…",[this]{choose_vault();}},{"_New Vault…",[this]{new_vault();}},{"Recent _Vaults…",[this]{recent_dialog();}},{"New Note… (Ctrl+N)",[this]{new_note();}},{"Quick Switcher (Ctrl+O)",[this]{switcher();}},{"Save (Ctrl+S)",[this]{if(!reading) save();}},{"Reload from Disk (Ctrl+Shift+R)",[this]{reload_disk();}},{"_Rename… (F2)",[this]{rename_dialog();}},{"Move Note… (F6)",[this]{relocate_note(false);}},{"_Archive Note",[this]{relocate_note(true);}},{"S_upersede With…",[this]{supersede_dialog();}},{"_Quit",[this]{close();}}});
        menu("_Edit",{{"Insert Template… (Ctrl+Shift+I)",[this]{insert_template();}},{"Highlight (Ctrl+Shift+H)",[this]{edit_highlight();}},{"_Undo",[this]{if(!reading&&buffer->can_undo()) buffer->undo();}},{"_Redo",[this]{if(!reading&&buffer->can_redo()) buffer->redo();}},{"Cu_t",[this]{if(!reading) buffer->cut_clipboard(Gtk::Clipboard::get());}},{"_Copy",[this]{if(reading) reading_buffer->copy_clipboard(Gtk::Clipboard::get());else buffer->copy_clipboard(Gtk::Clipboard::get());}},{"_Paste",[this]{if(!reading) buffer->paste_clipboard(Gtk::Clipboard::get());}}});
        menu("_View",{{"Highlights… (Ctrl+Shift+Y)",[this]{highlights_dialog();}},{"Focus _Editor",[this]{focus_content();}}});
        auto view_item=dynamic_cast<Gtk::MenuItem*>(menubar.get_children().back());
        auto submenu=dynamic_cast<Gtk::Menu*>(view_item->get_submenu());
        reading_item=Gtk::manage(new Gtk::CheckMenuItem("_Reading View (Ctrl+E)",true));
        submenu->prepend(*reading_item);
        reading_item->signal_toggled().connect([this]{if(reading_item->get_active()!=reading) toggle_reading();});
        menu("_Go",{{"Quick Switcher (Ctrl+O)",[this]{switcher();}},{"Follow Link (Alt+Enter)",[this]{follow_current();}},
            {"Search Notes… (Ctrl+Shift+F)",[this]{search_dialog();}},{"Backlinks (Ctrl+Shift+B)",[this]{focus_backlinks();}},
            {"Notes (Ctrl+Shift+E)",[this]{focus_sidebar(false);}},{"Tags (Ctrl+Shift+T)",[this]{focus_sidebar(true);}},
            {"Unlinked Mentions (Ctrl+Shift+M)",[this]{focus_backlinks(true);}},{"Today's Note (Ctrl+D)",[this]{today_note();}},{"Previous Daily Note (Alt+Left)",[this]{adjacent_daily(false);}},{"Next Daily Note (Alt+Right)",[this]{adjacent_daily(true);}}});
        menu("_Help",{{"_About",[this]{Gtk::AboutDialog dialog;dialog.set_transient_for(*this);dialog.set_program_name("LCOS Notes");dialog.set_version("1.1.0");dialog.set_copyright("Copyright 2026 Lee Harrington");dialog.set_license_type(Gtk::LICENSE_CUSTOM);dialog.set_wrap_license(true);dialog.set_license("Licensed under the Apache License, Version 2.0 (the \"License\"); you may not use this program except in compliance with the License. You may obtain a copy of the License at https://www.apache.org/licenses/LICENSE-2.0\n\nUnless required by applicable law or agreed to in writing, software distributed under the License is distributed on an \"AS IS\" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.");dialog.set_comments("Offline Markdown notes for LCOS and X11 desktops. Apache-2.0.");dialog.run();}}});
        layout.pack_start(menubar,Gtk::PACK_SHRINK);vault_label.set_text(vault.root.string()); vault_label.set_xalign(0); layout.pack_start(vault_label,Gtk::PACK_SHRINK);layout.pack_start(panes);layout.pack_end(status,Gtk::PACK_SHRINK);
        tree.set_model(store);tree.append_column("Notes",columns.label);tree.set_headers_visible(false);
        tree_scroll.add(tree);tree_scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        sidebar.append_page(tree_scroll,"Notes");sidebar.append_page(tags_scroll,"Tags");
        outline_tree.set_model(outline_store);outline_tree.append_column("Outline",columns.label);outline_tree.set_headers_visible(false);outline_scroll.add(outline_tree);sidebar.append_page(outline_scroll,"Outline");
        outline_tree.signal_row_activated().connect([this](const Gtk::TreeModel::Path&,Gtk::TreeViewColumn*){activate_outline();});
        panes.pack1(sidebar,false,false);panes.pack2(content,true,false);panes.set_position(190);
        content.pack1(views,true,false);content.pack2(backlinks_box,false,false);content.set_position(std::max(100,width-502));
        tags_tree.set_model(tag_store);tags_tree.append_column("Tags",columns.label);tags_tree.set_headers_visible(false);
        tags_scroll.add(tags_tree);tags_scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        backlinks_tree.set_model(backlink_store);backlinks_tree.append_column("Source",columns.label);
        backlinks_tree.append_column("Text",columns.text);
        for(auto column:backlinks_tree.get_columns()) column->set_resizable(true);
        backlinks_scroll.add(backlinks_tree);backlinks_scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        backlinks_box.set_size_request(300,-1);
        backlinks_box.pack_start(backlinks_split);
        backlinks_upper.pack_start(backlinks_label,Gtk::PACK_SHRINK);backlinks_upper.pack_start(backlinks_scroll);
        mentions_tree.set_model(mention_store);mentions_tree.append_column("Source",columns.label);mentions_tree.append_column("Text",columns.text);
        for(auto column:mentions_tree.get_columns()) column->set_resizable(true);
        mentions_scroll.add(mentions_tree);mentions_scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        mentions_lower.pack_start(mentions_label,Gtk::PACK_SHRINK);mentions_lower.pack_start(mentions_scroll);
        backlinks_split.pack1(backlinks_upper,true,false);backlinks_split.pack2(mentions_lower,true,false);
        backlinks_split.set_position(std::max(150,(height-60)*2/3));
        mentions_tree.signal_row_activated().connect([this](const Gtk::TreeModel::Path&,Gtk::TreeViewColumn*){open_backlink(true);});
        backlinks_tree.signal_row_activated().connect([this](const Gtk::TreeModel::Path&,Gtk::TreeViewColumn*){open_backlink();});
        tags_tree.signal_row_activated().connect([this](const Gtk::TreeModel::Path&,Gtk::TreeViewColumn*) {activate_tag();});
        buffer->set_language(Gsv::LanguageManager::get_default()->get_language("markdown"));
        buffer->set_highlight_syntax(true);
        resolved_tag=buffer->create_tag("wikilink-resolved");resolved_tag->property_foreground()="#205ca8";resolved_tag->property_underline()=Pango::UNDERLINE_SINGLE;
        unresolved_tag=buffer->create_tag("wikilink-unresolved");unresolved_tag->property_foreground()="#a33b24";unresolved_tag->property_underline()=Pango::UNDERLINE_SINGLE;
        editor.set_buffer(buffer);editor.set_show_line_numbers(true);editor.set_wrap_mode(Gtk::WRAP_WORD_CHAR);editor.set_monospace(true);
        editor_scroll.add(editor);editor_scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        views.add(editor_scroll,"editor");reading_container.pack_start(properties_box,Gtk::PACK_SHRINK);reading_container.pack_start(reading_scroll);views.add(reading_container,"reading");
        reading_view.set_buffer(reading_buffer);reading_view.set_editable(false);reading_view.set_cursor_visible(true);
        reading_view.signal_size_allocate().connect([this](Gtk::Allocation&) {
            resize_reading_images();
            if(reading_scroll_pending) scroll_reading_caret();
        });
        reading_view.set_wrap_mode(Gtk::WRAP_WORD_CHAR);reading_view.set_left_margin(12);reading_view.set_right_margin(12);reading_scroll.add(reading_view);
        reading_scroll.set_policy(Gtk::POLICY_AUTOMATIC,Gtk::POLICY_AUTOMATIC);
        for(auto name:{"h1","h2","h3","h4","h5","h6","em","strong","code","codeblock","quote","url","link","unresolved","rule","strike","task","done","table","th","highlight","callout-note","callout-tip","callout-warning","callout-danger","callout-question","callout-quote","callout-title","folded","image","embed"}) reading_tags[name]=reading_buffer->create_tag(name);
        for(int i=1;i<=6;++i) {auto tag=reading_tags["h"+std::to_string(i)];tag->property_weight()=Pango::WEIGHT_BOLD;tag->property_scale()=1.7-0.1*i;}
        reading_tags["highlight"]->property_background()="#FFE066";
        reading_tags["callout-note"]->property_paragraph_background()="#E3EEFB";
        reading_tags["callout-tip"]->property_paragraph_background()="#E2F5E7";
        reading_tags["callout-warning"]->property_paragraph_background()="#FFF1D6";
        reading_tags["callout-danger"]->property_paragraph_background()="#FBE2E2";
        reading_tags["callout-question"]->property_paragraph_background()="#EFE6FA";
        reading_tags["callout-quote"]->property_paragraph_background()="#EEEEEE";
        reading_tags["callout-title"]->property_weight()=Pango::WEIGHT_BOLD;
        reading_tags["folded"]->property_invisible()=true;
        reading_tags["strike"]->property_strikethrough()=true;
        reading_tags["done"]->property_strikethrough()=true;reading_tags["done"]->property_foreground()="#666666";
        reading_tags["task"]->property_foreground()="#205ca8";
        reading_tags["task"]->property_weight()=Pango::WEIGHT_BOLD;
        reading_tags["task"]->property_scale()=1.3;
        reading_tags["table"]->property_family()="monospace";reading_tags["th"]->property_weight()=Pango::WEIGHT_BOLD;
        reading_tags["em"]->property_style()=Pango::STYLE_ITALIC;
        reading_tags["strong"]->property_weight()=Pango::WEIGHT_BOLD;
        for(auto name:{"code","codeblock"}) {reading_tags[name]->property_family()="monospace";reading_tags[name]->property_background()="#eeeeea";}
        for(auto name:{"code","codeblock","highlight"})
            reading_tags[name]->set_priority(reading_buffer->get_tag_table()->get_size()-1);
        reading_tags["quote"]->property_left_margin()=36;reading_tags["quote"]->property_foreground()="#666666";
        reading_tags["rule"]->property_foreground()="#666666";
        for(auto name:{"url","link","unresolved"}) {reading_tags[name]->property_underline()=Pango::UNDERLINE_SINGLE;reading_tags[name]->property_foreground()=std::string(name)=="unresolved"?"#a33b24":"#205ca8";}
        reading_view.signal_button_press_event().connect([this](GdkEventButton* event) {
            if(event->button!=1 || (event->state&(GDK_SHIFT_MASK|GDK_CONTROL_MASK|GDK_MOD1_MASK))) return false;
            int x,y;reading_view.window_to_buffer_coords(reading_view.get_window_type(Glib::wrap(event->window,true)),event->x,event->y,x,y);
            Gtk::TextBuffer::iterator at;int trailing;reading_view.get_iter_at_position(at,trailing,x,y);
            int clicked=at.get_offset()+trailing;
            for(auto& title:rendered.spans) if(title.style=="callout-title"&&title.start<=clicked&&clicked<=title.end) {
                size_t index=0;
                for(auto& fold:rendered.spans) if(fold.style=="folded") {
                    if(fold.start==title.end) {
                        fold_closed[index]=!fold_closed[index];update_folds();
                        reading_buffer->place_cursor(reading_buffer->get_iter_at_offset(clicked));return true;
                    }
                    ++index;
                }
            }
            // A click past the line's text must not follow the last link on it.
            Gdk::Rectangle rect;reading_view.get_iter_location(at,rect);
            if(x<rect.get_x()||x>=rect.get_x()+rect.get_width()||y<rect.get_y()||y>=rect.get_y()+rect.get_height()) return false;
            if(toggle_task(at.get_offset())) return true;
            for(auto& l:rendered.links) if(l.start<=at.get_offset()&&at.get_offset()<l.end) {follow_reading(at.get_offset());return true;}
            return false;
        },false);
        editor.set_sensitive(false);
        tree.signal_row_activated().connect([this](const Gtk::TreeModel::Path&,Gtk::TreeViewColumn*) {activate_tree();});
        buffer->signal_changed().connect([this]{if(!loading) {
            update_title();styling.disconnect();
            styling=Glib::signal_timeout().connect([this]{style_links();refresh_outline();return false;},180);
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
        start_monitoring();
        remember();
    }
};
int main(int argc,char** argv) {
    if(!g_getenv("GDK_BACKEND")) g_setenv("GDK_BACKEND","x11",false);
    g_setenv("GTK_CSD","0",true);
    try {
        std::string root,note;bool capture_mode=false;
        for(int i=1;i<argc;++i) {
            std::string arg=argv[i];
            if(arg=="--capture"&&!capture_mode) capture_mode=true;
            else if(arg=="--vault" && i+1<argc && root.empty()) root=argv[++i];
            else if(arg.size() && arg[0]!='-' && note.empty()) note=arg;
            else throw std::runtime_error("usage: lcos-notes [--vault DIR [NOTE]]");
        }
        auto app=Gtk::Application::create("com.leebase.LcosNotes",Gio::APPLICATION_NON_UNIQUE);Gsv::init();
        Gtk::Settings::get_default()->property_gtk_dialogs_use_header()=false;
        if(root.empty()) {
            std::ifstream last(fs::path(Glib::get_user_config_dir())/"lcos-notes"/"last-vault");std::getline(last,root);
            if(!fs::is_directory(root)) {
                if(capture_mode) throw std::runtime_error("no vault");
                Gtk::FileChooserDialog chooser("Open Vault",Gtk::FILE_CHOOSER_ACTION_SELECT_FOLDER);
                chooser.add_button("_Cancel",Gtk::RESPONSE_CANCEL);chooser.add_button("_Open",Gtk::RESPONSE_OK);
                if(chooser.run()!=Gtk::RESPONSE_OK) return 0;
                root=chooser.get_filename();
            }
        }
        if(capture_mode) {
            Vault v(root);auto real=fs::canonical(v.root).string();gchar* digest=g_compute_checksum_for_string(G_CHECKSUM_SHA256,real.c_str(),real.size());const char* state_env=g_getenv("XDG_STATE_HOME");fs::path state=state_env&&*state_env?fs::path(state_env):fs::path(Glib::get_home_dir())/".local/state";auto choice_path=state/"lcos-notes"/digest/"capture";g_free(digest);
            Gtk::Window window;window.set_title("Capture — Notes");window.set_default_size(480,300);Gtk::Box box(Gtk::ORIENTATION_VERTICAL,8);Gtk::ScrolledWindow scroll;Gtk::TextView view;scroll.add(view);box.pack_start(scroll);Gtk::RadioButton today("_Today's note",true), inbox("_Inbox",true);inbox.join_group(today);box.pack_start(today,Gtk::PACK_SHRINK);box.pack_start(inbox,Gtk::PACK_SHRINK);std::ifstream choice(choice_path);std::string saved;std::getline(choice,saved);if(saved=="inbox")inbox.set_active();Gtk::Label error;box.pack_start(error,Gtk::PACK_SHRINK);Gtk::ButtonBox buttons;Gtk::Button cancel("_Cancel",true),submit("_Capture",true);buttons.pack_start(cancel);buttons.pack_start(submit);box.pack_start(buttons,Gtk::PACK_SHRINK);window.add(box);
            auto perform=[&]{try{auto text=view.get_buffer()->get_text().raw();capture(v,clock_now(false),text,inbox.get_active());fs::create_directories(choice_path.parent_path());std::ofstream(choice_path)<<(inbox.get_active()?"inbox":"today");window.hide();}catch(const std::exception& e){if(std::string(e.what())!="nothing to capture")error.set_text(std::string("refused: ")+e.what());}};submit.signal_clicked().connect(perform);cancel.signal_clicked().connect([&]{window.hide();});window.signal_key_press_event().connect([&](GdkEventKey* e){if(e->keyval==GDK_KEY_Escape){window.hide();return true;}if((e->state&GDK_MOD1_MASK)&&(e->keyval==GDK_KEY_i||e->keyval==GDK_KEY_I||e->keyval==GDK_KEY_t||e->keyval==GDK_KEY_T)){if(e->keyval==GDK_KEY_i||e->keyval==GDK_KEY_I)inbox.set_active();else today.set_active();view.grab_focus();return true;}if((e->state&GDK_CONTROL_MASK)&&(e->keyval==GDK_KEY_Return||e->keyval==GDK_KEY_KP_Enter)){perform();return true;}return false;},false);window.show_all();view.grab_focus();return app->run(window);
        }
        Window window(prepare_vault(root),note);return app->run(window);
    } catch(const std::exception& e) {std::cerr<<"refused: "<<e.what()<<'\n';return 2;}
}
