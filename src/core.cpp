// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Lee Harrington
#include "core.hpp"
#include <glib.h>
#include <algorithm>
#include <cerrno>
#include <cstring>
#include <fcntl.h>
#include <memory>
#include <map>
#include <regex>
#include <set>
#include <fstream>
#include <stdexcept>
#include <tuple>
#include <unistd.h>
namespace notes {
static void fail(const std::string& message) { throw std::runtime_error(message); }
std::string trim(std::string s) {
    auto a = s.find_first_not_of(' ');
    if (a == std::string::npos) return "";
    return s.substr(a, s.find_last_not_of(' ') - a + 1);
}
std::string fold(const std::string& s) {
    if (!g_utf8_validate(s.data(), s.size(), nullptr)) fail("invalid UTF-8");
    std::unique_ptr<char, decltype(&g_free)> n(g_utf8_normalize(s.data(), s.size(), G_NORMALIZE_NFC), g_free);
    std::unique_ptr<char, decltype(&g_free)> p(g_utf8_casefold(n.get(), -1), g_free);
    return p.get();
}
std::string quote(const std::string& s) {
    std::string out = "\"";
    const char* hex = "0123456789abcdef";
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') { out += '\\'; out += c; }
        else if (c < 32) { out += "\\u00"; out += hex[c >> 4]; out += hex[c & 15]; }
        else out += c;
    }
    return out + '"';
}
std::string json(const Maybe& s) { return s ? quote(*s) : "null"; }
bool is_note(const std::string& s) { return s.size() >= 3 && s.substr(s.size()-3) == ".md"; }
static std::string strip(std::string s) {
    if (s.size() >= 3 && s[s.size()-3]=='.' &&
        (s[s.size()-2]=='m' || s[s.size()-2]=='M') &&
        (s.back()=='d' || s.back()=='D')) s.resize(s.size()-3);
    return s;
}
static std::string directory(const std::string& s) { return fs::path(s).parent_path().generic_string(); }
static int depth(const std::string& s) { return std::count(s.begin(), s.end(), '/'); }
static int chars(const std::string& s) { return g_utf8_strlen(s.data(), s.size()); }
Link parts(std::string s) {
    Link l;
    auto p = s.find('|');
    if (p != std::string::npos) { l.alias = trim(s.substr(p+1)); s.resize(p); }
    p = s.find('#');
    if (p != std::string::npos) { l.heading = trim(s.substr(p+1)); s.resize(p); }
    l.target = trim(s);
    return l;
}
// Byte mask shared by link and tag parsing. Only matched inline spans hide text.
static std::vector<bool> prose(const std::string& text) {
    std::vector<bool> mask(text.size(),true);
    char fence=0; size_t fence_len=0;
    for(size_t start=0;start<text.size();) {
        auto end=text.find('\n',start); if(end==std::string::npos) end=text.size();
        auto s=text.substr(start,end-start); auto first=s.find_first_not_of(' ');
        size_t run=0; char c=first==std::string::npos?0:s[first];
        if(c=='`'||c=='~') while(first+run<s.size()&&s[first+run]==c) ++run;
        bool hidden=bool(fence);
        if(fence) {if(c==fence&&run>=fence_len) fence=0;}
        else if(run>=3) {fence=c;fence_len=run;hidden=true;}
        if(hidden) std::fill(mask.begin()+start,mask.begin()+end,false);
        else for(size_t i=start;i<end;) {
            // A recognized link is one token, as in the U1 scanner: backticks
            // in its heading or alias do not start spans in following prose.
            bool embed=text[i]=='!'&&text.compare(i+1,2,"[[")==0;
            size_t open=i+(embed?1:0);
            if(text.compare(open,2,"[[")==0) {
                auto close=text.find("]]",open+2);
                if(close<end&&close>open+2&&text.substr(open+2,close-open-2).find_first_of("[]\r\n")==std::string::npos) {i=close+2;continue;}
            }
            if(text[i]!='`') {++i;continue;}
            size_t n=1;while(i+n<end&&text[i+n]=='`') ++n;
            size_t j=i+n;bool found=false;
            while(j<end) {
                if(text[j]!='`') {++j;continue;}
                size_t m=1;while(j+m<end&&text[j+m]=='`') ++m;
                if(m==n) {std::fill(mask.begin()+i,mask.begin()+j+m,false);i=j+m;found=true;break;}
                j+=m;
            }
            if(!found) i+=n;
        }
        start=end+1;
    }
    return mask;
}
std::vector<Link> parse(const std::string& text) {
    std::vector<Link> out; auto mask=prose(text);
    int line=1,base=0;size_t start=0;
    while(start<text.size()) {
        auto end=text.find('\n',start);if(end==std::string::npos) end=text.size();
        for(size_t i=start;i<end;) {
            if(!mask[i]) {++i;continue;}
            bool embed=text[i]=='!'&&text.compare(i+1,2,"[[")==0;
            size_t open=i+(embed?1:0);
            if(text.compare(open,2,"[[")==0) {
                auto close=text.find("]]",open+2);
                if(close<end) {
                    auto inner=text.substr(open+2,close-open-2);
                    if(!inner.empty()&&inner.find_first_of("[]\r\n")==std::string::npos) {
                        auto l=parts(inner);l.embed=embed;l.raw=text.substr(i,close+2-i);
                        l.line=line;l.col=chars(text.substr(start,i-start))+1;
                        l.offset=base+l.col-1;l.length=chars(l.raw);out.push_back(l);
                        i=close+2;continue;
                    }
                }
            }
            ++i;
        }
        base+=chars(text.substr(start,end-start))+(end<text.size()?1:0);
        start=end+1;++line;
    }
    return out;
}

static Maybe percent_decode(const std::string& s) {
    std::string out;
    for(size_t i=0;i<s.size();++i) {
        if(s[i]=='%'&&i+2<s.size()&&g_ascii_isxdigit(s[i+1])&&g_ascii_isxdigit(s[i+2])) {
            out+=char(g_ascii_xdigit_value(s[i+1])*16+g_ascii_xdigit_value(s[i+2]));i+=2;
        } else out+=s[i];
    }
    // U+0000 is a valid decoded code point, although it cannot name a file.
    // GLib's length-bounded validator rejects embedded NUL, so validate each run.
    for(size_t start=0;start<out.size();) {
        auto end=out.find('\0',start);if(end==std::string::npos) end=out.size();
        if(!g_utf8_validate(out.data()+start,end-start,nullptr)) return {};
        start=end+1;
    }
    return out;
}
std::vector<Link> parse_markdown(const std::string& text) {
    auto mask=prose(text);
    for(auto& w:parse(text)) {
        auto begin=g_utf8_offset_to_pointer(text.data(),w.offset)-text.data();
        std::fill(mask.begin()+begin,mask.begin()+begin+w.raw.size(),false);
    }
    std::vector<Link> out;int line=1,base=0;
    static const std::regex scheme("^[A-Za-z][A-Za-z0-9+.-]*:");
    for(size_t start=0;start<text.size();++line) {
        auto end=text.find('\n',start);if(end==std::string::npos) end=text.size();
        for(size_t i=start;i<end;) {
            if(text[i]!='['||(i>start&&(text[i-1]=='!'||text[i-1]=='\\'))) {++i;continue;}
            size_t j=i+1;while(j<end&&std::strchr("[]\r",text[j])==nullptr) ++j;
            if(j+1>=end||text[j]!=']'||text[j+1]!='(') {++i;continue;}
            size_t k=j+2,m=k,finish;bool angle=k<end&&text[k]=='<';std::string dest;
            if(angle) {
                m=k+1;while(m<end&&std::strchr("<>\r",text[m])==nullptr) ++m;
                if(m+1>=end||text[m]!='>'||text[m+1]!=')') {++i;continue;}
                dest=text.substr(k+1,m-k-1);finish=m+2;
            } else {
                while(m<end&&std::strchr(" \t()<\r",text[m])==nullptr) ++m;
                if(m==k||m>=end||text[m]!=')') {++i;continue;}
                dest=text.substr(k,m-k);finish=m+1;
            }
            if(!std::all_of(mask.begin()+i,mask.begin()+finish,[](bool b){return b;})||
               std::regex_search(dest,scheme)||dest.compare(0,2,"//")==0) {++i;continue;}
            auto hash=dest.find('#');auto path=percent_decode(dest.substr(0,hash));Maybe head;
            if(hash!=std::string::npos) head=percent_decode(dest.substr(hash+1));
            if(!path||(hash!=std::string::npos&&!head)||(path->empty()&&hash==std::string::npos)) {++i;continue;}
            Link l;l.markdown=true;l.angle=angle;l.text=text.substr(i+1,j-i-1);l.target=*path;
            if(head) l.heading=trim(*head);
            l.raw=text.substr(i,finish-i);l.line=line;l.col=chars(text.substr(start,i-start))+1;
            l.offset=base+l.col-1;l.length=chars(l.raw);out.push_back(l);i=finish;
        }
        base+=chars(text.substr(start,end-start))+(end<text.size()?1:0);start=end+1;
    }
    return out;
}
std::vector<Link> parse_all(const std::string& text) {
    auto out=parse(text),md=parse_markdown(text);out.insert(out.end(),md.begin(),md.end());
    std::sort(out.begin(),out.end(),[](auto& a,auto& b){return a.offset<b.offset;});return out;
}
static Maybe collapse(const std::string& path) {
    std::vector<std::string> parts;
    for(size_t i=0;i<=path.size();) {
        auto end=path.find('/',i);if(end==std::string::npos) end=path.size();
        auto p=path.substr(i,end-i);
        if(p=="..") {if(parts.empty()) return {};parts.pop_back();}
        else if(!p.empty()&&p!=".") parts.push_back(p);
        i=end+1;
    }
    std::string out;for(auto& p:parts) {if(!out.empty()) out+='/';out+=p;}return out;
}
std::string creation_target(const std::string& source,const Link& l) {
    if(!l.markdown) return l.target;
    Maybe path;
    if(l.target.compare(0,1,"/")!=0) path=collapse(directory(source)+"/"+l.target);
    if(!path) path=collapse(l.target);
    if(!path) fail("path leaves vault");
    return *path;
}
static Maybe resolve_markdown(const std::vector<std::string>& files,const std::string& source,const std::string& path) {
    if(path.empty()) return source;
    if(path.find('\0')!=std::string::npos) return {};
    std::vector<std::string> candidates;
    auto add=[&](Maybe p) {
        if(!p||p->empty()) return;
        candidates.push_back(*p);if(strip(*p)==*p) candidates.push_back(*p+".md");
    };
    if(path[0]!='/') add(collapse(directory(source)+"/"+path));
    add(collapse(path));
    for(auto& candidate:candidates) {
        if(std::find(files.begin(),files.end(),candidate)!=files.end()) return candidate;
        auto key=fold(candidate);for(auto& f:files) if(fold(f)==key) return f;
    }
    return {};
}
Vault::Vault(fs::path path) : root(fs::absolute(path).lexically_normal()) {
    if (!fs::is_directory(root)) fail("vault is not a directory");
    if (root!=root.root_path() && root.filename().empty()) root=root.parent_path();
}
static std::vector<std::string> entries(const fs::path& root, bool directories) {
    std::vector<std::string> out;
    for (fs::recursive_directory_iterator i(root), end; i!=end; ++i) {
        auto name=i->path().filename().string();
        auto st=i->symlink_status();
        if (name[0]=='.' || fs::is_symlink(st)) { i.disable_recursion_pending(); continue; }
        if (directories ? fs::is_directory(st) : fs::is_regular_file(st))
            out.push_back(i->path().lexically_relative(root).generic_string());
    }
    std::sort(out.begin(),out.end()); return out;
}
std::vector<std::string> Vault::files() const {return entries(root,false);}
std::vector<std::string> Vault::directories() const {return entries(root,true);}
std::vector<std::string> Vault::notes() const {
    auto all=files(); all.erase(std::remove_if(all.begin(),all.end(),[](auto& s){return !is_note(s);}),all.end()); return all;
}
void Vault::require_note(const std::string& path) const {
    auto all=notes(); if (!std::binary_search(all.begin(),all.end(),path)) fail("source is not an existing note");
}
static Maybe resolve_files(const std::vector<std::string>& all, const std::string& source, std::string target) {
    if (target.empty()) return source;
    auto match = [&](std::string needle, bool note) -> Maybe {
        needle=fold(needle); std::vector<std::string> exact, suffix;
        for (auto& path:all) {
            if (is_note(path)!=note) continue;
            std::string candidate=fold(note ? path.substr(0,path.size()-3) : path);
            if (needle.find('/')==std::string::npos) {
                if (fs::path(candidate).filename().string()==needle) exact.push_back(path);
            } else if (candidate==needle) exact.push_back(path);
            else if (candidate.size()>needle.size() && candidate.compare(candidate.size()-needle.size(),needle.size(),needle)==0 && candidate[candidate.size()-needle.size()-1]=='/') suffix.push_back(path);
        }
        auto& matches=exact.empty()?suffix:exact;
        std::sort(matches.begin(),matches.end(),[&](auto& a,auto& b){
            return std::make_tuple(directory(a)!=directory(source),depth(a),a) < std::make_tuple(directory(b)!=directory(source),depth(b),b);
        });
        if(matches.empty()) return {};
        return matches.front();
    };
    target=strip(target);
    auto note=match(target,true); if(note) return note;
    auto name=fs::path(target).filename().string(); auto dot=name.rfind('.');
    if(dot==std::string::npos || name.size()-dot-1<1 || name.size()-dot-1>5) return {};
    for(size_t i=dot+1;i<name.size();++i) if(!g_ascii_isalnum(name[i])) return {};
    return match(target,false);
}
Maybe Vault::resolve(const std::string& source, std::string target) const {
    return resolve_files(files(),source,target);
}
std::vector<Link> Vault::links(const std::string& source, const std::string& text) const {
    auto all=files();auto out=parse(text); for(auto& l:out) l.resolved=resolve_files(all,source,l.target); return out;
}
std::vector<Link> Vault::mdlinks(const std::string& source,const std::string& text) const {
    auto all=files();auto out=parse_markdown(text);for(auto& l:out) l.resolved=resolve_markdown(all,source,l.target);return out;
}
std::vector<Link> Vault::all_links(const std::string& source,const std::string& text) const {
    auto all=files();auto out=parse_all(text);
    for(auto& l:out) l.resolved=l.markdown?resolve_markdown(all,source,l.target):resolve_files(all,source,l.target);
    return out;
}
std::vector<std::string> Vault::search(const std::string& query) const {
    auto q=fold(query); std::vector<std::string> out;
    for(auto& path:notes()) {
        auto p=fold(path.substr(0,path.size()-3)); // Match Unicode code points after case folding.
        const char* wanted=q.c_str();
        for(const char* c=p.c_str();*c && *wanted;c=g_utf8_next_char(c))
            if(g_utf8_get_char(c)==g_utf8_get_char(wanted)) wanted=g_utf8_next_char(wanted);
        if(!*wanted) out.push_back(path);
    }
    auto rank=[&](const std::string& path) {
        auto n=fold(fs::path(path).filename().string()); n.resize(n.size()-3);
        return n==q ? 0 : n.find(q)==0 ? 1 : n.find(q)!=std::string::npos ? 2 : 3;
    };
    std::sort(out.begin(),out.end(),[&](auto& a,auto& b){return std::make_tuple(rank(a),depth(a),a)<std::make_tuple(rank(b),depth(b),b);});
    if(out.size()>50) out.resize(50);
    return out;
}
// Directory descriptors prevent following vault-internal symlinks during writes.
struct FD {
    int n;
    explicit FD(int value):n(value){if(n<0) fail(std::strerror(errno));}
    ~FD(){close(n);}
    FD(const FD&)=delete; FD& operator=(const FD&)=delete;
};
static int parent_fd(const Vault& v,const std::string& path,std::vector<fs::path>* made=nullptr) {
    int fd=open(v.root.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC);
    if(fd<0) fail("cannot open vault");
    fs::path relative;
    for(auto& part:fs::path(path).parent_path()) {
        auto s=part.string();relative/=part;
        if(s.empty()||s[0]=='.') {close(fd);fail("unsafe directory");}
        int next=openat(fd,s.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        if(next<0&&errno==ENOENT&&made) {
            if(mkdirat(fd,s.c_str(),0777)==0) made->push_back(v.root/relative);
            else if(errno!=EEXIST) {close(fd);fail("cannot restore note directory");}
            next=openat(fd,s.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        }
        close(fd); if(next<0) fail("unsafe or missing directory"); fd=next;
    }
    return fd;
}
static std::string validated_target(std::string target,bool note=true) {
    if(note) target=strip(target);
    if(target.empty() || target[0]=='/') fail("empty or absolute target");
    fold(target);
    for(const char* c=target.c_str();*c;c=g_utf8_next_char(c)) {
        auto ch=g_utf8_get_char(c);
        if(g_unichar_iscntrl(ch) || (ch<128 && std::strchr("*\"\\<>:|?#^",ch))) fail("invalid character in target");
    }
    size_t begin=0;
    while(begin<=target.size()) {
        size_t end=target.find('/',begin); if(end==std::string::npos) end=target.size();
        auto segment=target.substr(begin,end-begin);
        if(segment.empty() || segment[0]=='.') fail("unsafe path segment");
        begin=end+1;
    }
    return target;
}
std::pair<std::string,bool> Vault::create(std::string target) const {
    const auto original_target=trim(target);
    target=validated_target(original_target);
    if(auto found=resolve("",original_target); found && is_note(*found)) return {*found,false};
    std::string path=target+".md";
    // Inspect the entire existing prefix before making any directories.
    fs::path current=root;
    for(auto& part:fs::path(path)) {
        current/=part;
        auto st=fs::symlink_status(current);
        if(fs::is_symlink(st)) fail("symlink in creation path");
        if(fs::exists(st) && (current==root/path || !fs::is_directory(st))) fail("creation path already exists");
    }
    std::vector<fs::path> made;
    try {
        current=root;
        for(auto& part:fs::path(path).parent_path()) {
            current/=part; if(fs::create_directory(current)) made.push_back(current);
        }
        FD dir(parent_fd(*this,path));
        FD file(openat(dir.n,fs::path(path).filename().c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0666));
    } catch(...) {for(auto it=made.rbegin();it!=made.rend();++it) {std::error_code ec;fs::remove(*it,ec);} throw;}
    return {path,true};
}
static std::string read_fd(int fd) {
    std::string out; char data[16384]; ssize_t n;
    while((n=read(fd,data,sizeof data))>0) out.append(data,n);
    if(n<0) fail("cannot read note");
    return out;
}
static bool same(const struct stat& a,const struct stat& b) {
    return a.st_dev==b.st_dev && a.st_ino==b.st_ino && a.st_size==b.st_size &&
        a.st_mtim.tv_sec==b.st_mtim.tv_sec && a.st_mtim.tv_nsec==b.st_mtim.tv_nsec &&
        a.st_ctim.tv_sec==b.st_ctim.tv_sec && a.st_ctim.tv_nsec==b.st_ctim.tv_nsec;
}
void Document::load(const Vault& vault,const std::string& relative) {
    vault.require_note(relative); FD dir(parent_fd(vault,relative));
    FD file(openat(dir.n,fs::path(relative).filename().c_str(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC));
    struct stat before{},after{};
    if(fstat(file.n,&before)!=0 || !S_ISREG(before.st_mode)) fail("not a regular note");
    auto bytes=read_fd(file.n);
    if(fstat(file.n,&after)!=0 || !same(before,after)) fail("note changed while loading");
    if(!g_utf8_validate(bytes.data(),bytes.size(),nullptr)) fail("note is not UTF-8 text");
    missing=false; stamp=after; original=bytes; text=bytes; path=relative;
}
bool Document::changed(const Vault& vault) const {
    struct stat current{};
    if(lstat((vault.root/path).c_str(),&current)!=0) return !missing;
    return missing||!same(current,stamp);
}
void Document::save(const Vault& vault,const std::string& contents) {
    if(contents==original&&!missing) {text=contents;return;}
    // Recover a deleted note even if its containing folder was removed or moved.
    // Only this recovery path creates parents; existing paths still use no-follow
    // directory descriptors. Remove newly made empty directories on refusal.
    struct Recovery {
        std::vector<fs::path> made;
        bool saved=false;
        ~Recovery() {if(!saved) for(auto it=made.rbegin();it!=made.rend();++it) {std::error_code ec;fs::remove(*it,ec);}}
    } recovery;
    FD dir(parent_fd(vault,path,missing?&recovery.made:nullptr)); auto name=fs::path(path).filename().string();
    auto unchanged=[&]() {
        int n=openat(dir.n,name.c_str(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
        if(n<0) return missing&&errno==ENOENT;
        FD file(n); struct stat st{};
        return !missing && fstat(file.n,&st)==0 && same(st,stamp) && read_fd(file.n)==original;
    };
    if(!unchanged()) fail("Changed on disk; not saved");
    std::string temp;
    int n=-1;
    for(int i=0;i<100 && n<0;++i) {
        temp=".lcos-notes-"+std::to_string(getpid())+"-"+std::to_string(i);
        n=openat(dir.n,temp.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600);
        if(n<0 && errno!=EEXIST) fail("cannot create save temporary file");
    }
    FD file(n);
    try {
        if(fchmod(file.n,stamp.st_mode&0777)!=0) fail("cannot preserve permissions");
        size_t written=0;
        while(written<contents.size()) {
            auto amount=write(file.n,contents.data()+written,contents.size()-written);
            if(amount<0 && errno==EINTR) continue;
            if(amount<=0) fail("cannot write note");
            written+=amount;
        }
        if(fsync(file.n)!=0) fail("cannot flush note");
        if(!unchanged()) fail("Changed on disk; not saved");
        if(renameat(dir.n,temp.c_str(),dir.n,name.c_str())!=0) fail("cannot replace note");
        fstat(file.n,&stamp); fsync(dir.n);
        missing=false; original=contents; text=contents;recovery.saved=true;
    } catch(...) {unlinkat(dir.n,temp.c_str(),0);throw;}
}
int heading_offset(const std::string& text,const std::string& heading) {
    if(heading.empty()||heading.find('\0')!=std::string::npos) return 0;
    if(heading[0]=='^') {
        auto id=trim(heading.substr(1));
        if(id.empty()||!std::all_of(id.begin(),id.end(),[](unsigned char c){return g_ascii_isalnum(c)||c=='-';})) return 0;
        char fence=0;size_t fence_len=0;int offset=0;
        for(size_t start=0;start<text.size();) {
            auto end=text.find('\n',start);if(end==std::string::npos) end=text.size();
            auto line=text.substr(start,end-start);if(!line.empty()&&line.back()=='\r') line.pop_back();
            auto first=line.find_first_not_of(' ');size_t run=0;char c=first==std::string::npos?0:line[first];
            if(c=='`'||c=='~') while(first+run<line.size()&&line[first+run]==c) ++run;
            bool hidden=bool(fence);
            if(fence) {if(c==fence&&run>=fence_len) fence=0;}
            else if(run>=3) {hidden=true;fence=c;fence_len=run;}
            auto last=line.find_last_not_of(" \t");line=last==std::string::npos?"":line.substr(0,last+1);
            auto marker=line.find_last_of(" \t");
            if(!hidden&&marker!=std::string::npos&&fold(line.substr(marker+1))==fold("^"+id)) return offset;
            offset+=chars(text.substr(start,end-start))+(end<text.size()?1:0);start=end+1;
        }
        return 0;
    }
    size_t start=0; int offset=0;
    while(start<text.size()) {
        auto end=text.find('\n',start); if(end==std::string::npos) end=text.size();
        auto line=text.substr(start,end-start); if(!line.empty() && line.back()=='\r') line.pop_back();
        size_t i=0; while(i<line.size() && line[i]==' ' && i<4) ++i;
        size_t hash=i; while(i<line.size() && line[i]=='#') ++i;
        size_t count=i-hash;
        if(hash<=3 && count>=1 && count<=6 && (i==line.size() || line[i]==' ' || line[i]=='\t')) {
            auto title=line.substr(i);
            auto first=title.find_first_not_of(" \t");
            title=first==std::string::npos ? "" : title.substr(first,title.find_last_not_of(" \t")-first+1);
            size_t tail=title.size(); while(tail>0 && title[tail-1]=='#') --tail;
            if(tail<title.size() && tail>0 && (title[tail-1]==' ' || title[tail-1]=='\t')) title=trim(title.substr(0,tail));
            if(fold(title)==fold(heading)) return offset;
        }
        offset+=chars(text.substr(start,end-start))+(end<text.size()?1:0); start=end+1;
    }
    return 0;
}
// Shared U2 operations.
static std::optional<std::string> utf8_note(const Vault& vault,const std::string& path) {
    std::ifstream in(vault.root/path,std::ios::binary);
    if(!in) fail("cannot read note");
    std::string text((std::istreambuf_iterator<char>(in)),{});
    if(!g_utf8_validate(text.data(),text.size(),nullptr)) return {};
    return text;
}
static bool tag_char(gunichar c) {return g_unichar_isalnum(c)||c=='_'||c=='-'||c=='/';}
static bool valid_tag(const std::string& s) {
    if(s.empty()||!g_utf8_validate(s.data(),s.size(),nullptr)) return false;
    bool non_digit=false;
    for(const char* p=s.c_str();*p;p=g_utf8_next_char(p)) {
        auto c=g_utf8_get_char(p);if(!tag_char(c)) return false;
        if(c<'0'||c>'9') non_digit=true;
    }
    return non_digit;
}
struct TagOccurrence {std::string tag;size_t start,end;};
static std::vector<TagOccurrence> tag_occurrences(const std::string& text) {
    std::vector<TagOccurrence> out;std::vector<std::string> lines;
    std::vector<size_t> starts;
    for(size_t start=0;start<text.size();) {
        auto end=text.find('\n',start);if(end==std::string::npos) end=text.size();
        auto line=text.substr(start,end-start);if(!line.empty()&&line.back()=='\r') line.pop_back();
        lines.push_back(line);starts.push_back(start);start=end+1;
    }
    size_t body=0,finish=0;
    if(!lines.empty()&&lines[0]=="---") {
        for(size_t i=1;i<lines.size();++i) if(lines[i]=="---"||lines[i]=="...") {finish=i;body=i+1;break;}
    }
    auto item=[&](size_t a,size_t b) {
        while(a<b&&g_ascii_isspace(text[a])) ++a;
        while(b>a&&g_ascii_isspace(text[b-1])) --b;
        if(b-a>=2&&((text[a]=='\''&&text[b-1]=='\'')||(text[a]=='"'&&text[b-1]=='"'))) {++a;--b;}
        if(a<b&&text[a]=='#') ++a;
        auto tag=text.substr(a,b-a);
        if(valid_tag(tag)) out.push_back({tag,a,b});
    };
    for(size_t i=1;i<finish;++i) {
        size_t key=lines[i].compare(0,5,"tags:")==0?5:lines[i].compare(0,4,"tag:")==0?4:0;
        if(!key) continue;
        size_t a=starts[i]+key,b=starts[i]+lines[i].size();
        while(a<b&&g_ascii_isspace(text[a])) ++a;
        while(b>a&&g_ascii_isspace(text[b-1])) --b;
        if(a==b) {
            while(i+1<finish) {
                auto at=lines[i+1].find_first_not_of(" \t");
                if(at==std::string::npos||lines[i+1].compare(at,2,"- ")!=0) break;
                ++i;item(starts[i]+at+2,starts[i]+lines[i].size());
            }
        } else {
            bool flow=text[a]=='[';
            if(flow) {if(text[b-1]!=']') continue;++a;--b;}
            size_t start=a;
            for(size_t j=a;j<=b;++j) if(j==b||text[j]==','||(!flow&&g_ascii_isspace(text[j]))) {item(start,j);start=j+1;}
        }
    }
    auto mask=prose(text);
    for(size_t n=body;n<lines.size();++n) {
        const auto& line=lines[n];
        for(size_t i=0;i<line.size();++i) {
            if(line[i]!='#'||!mask[starts[n]+i]||(i&&line[i-1]!=' '&&line[i-1]!='\t')) continue;
            size_t j=i+1;
            while(j<line.size()&&tag_char(g_utf8_get_char(line.data()+j))) j=g_utf8_next_char(line.data()+j)-line.data();
            auto tag=line.substr(i+1,j-i-1);if(valid_tag(tag)) out.push_back({tag,starts[n]+i+1,starts[n]+j});
            i=j?j-1:i;
        }
    }
    return out;
}
static std::vector<std::string> note_tags(const std::string& text) {
    std::vector<std::string> out;for(auto& t:tag_occurrences(text)) out.push_back(t.tag);return out;
}
std::vector<Tag> Vault::tags() const {
    std::map<std::string,Tag> all;std::set<std::string> explicit_tags;
    for(auto& path:notes()) if(auto text=utf8_note(*this,path)) {
        std::set<std::string> seen;
        for(auto& tag:note_tags(*text)) {
            auto key=fold(tag);
            if(explicit_tags.insert(key).second) all[key].tag=tag;
            for(std::string parent=tag;;) {
                auto k=fold(parent);auto& row=all[k];
                if(row.tag.empty()) row.tag=parent;
                if(seen.insert(k).second) {++row.count;row.notes.push_back(path);}
                auto slash=parent.rfind('/');if(slash==std::string::npos) break;
                parent.resize(slash);
            }
        }
    }
    std::vector<Tag> out;for(auto& row:all) out.push_back(row.second);return out;
}
std::vector<std::string> Vault::tagged(std::string tag) const {
    if(!tag.empty()&&tag[0]=='#') tag.erase(0,1);
    if(!valid_tag(tag)) fail("invalid tag");
    tag=fold(tag);std::vector<std::string> out;
    for(auto& path:notes()) if(auto text=utf8_note(*this,path)) {
        for(auto& t:note_tags(*text)) {
            auto key=fold(t);if(key==tag||key.compare(0,tag.size()+1,tag+"/")==0) {out.push_back(path);break;}
        }
    }
    return out;
}
static std::u32string lower_points(const std::string& s) {
    if(!g_utf8_validate(s.data(),s.size(),nullptr)) fail("invalid UTF-8");
    std::u32string out;
    for(const char* p=s.data();p<s.data()+s.size();p=g_utf8_next_char(p)) out+=g_unichar_tolower(g_utf8_get_char(p));
    return out;
}
static bool word_char(gunichar c) {return g_unichar_isalnum(c)||c=='_';}
static bool whole_word(const std::u32string& points,size_t a,size_t b) {
    return (!a||!word_char(points[a-1]))&&(b==points.size()||!word_char(points[b]));
}
std::vector<Match> Vault::find(const std::string& query,bool regex,bool word) const {
    if(query.empty()) fail("empty query");
    auto q=lower_points(query);std::vector<Match> out;
    GError* error=nullptr;
    std::unique_ptr<GRegex,decltype(&g_regex_unref)> pattern(regex?g_regex_new(query.c_str(),G_REGEX_CASELESS,G_REGEX_MATCH_DEFAULT,&error):nullptr,g_regex_unref);
    if(error) {std::string message=error->message;g_error_free(error);fail(message);}
    for(auto& path:notes()) if(auto text=utf8_note(*this,path)) {
        int number=0;
        for(size_t start=0;start<=text->size();) {
            auto end=text->find('\n',start);if(end==std::string::npos) end=text->size();
            auto line=text->substr(start,end-start);if(!line.empty()&&line.back()=='\r') line.pop_back();
            ++number;auto points=lower_points(line);size_t at=0;
            while(at<=points.size()) {
                size_t a,b;
                if(regex) {
                    GMatchInfo* info=nullptr;
                    auto byte=g_utf8_offset_to_pointer(line.data(),at)-line.data();
                    bool found=g_regex_match_full(pattern.get(),line.data(),line.size(),byte,G_REGEX_MATCH_DEFAULT,&info,&error);
                    if(error) {std::string message=error->message;g_error_free(error);if(info) g_match_info_free(info);fail(message);}
                    if(!found) {if(info) g_match_info_free(info);break;}
                    int x,y;g_match_info_fetch_pos(info,0,&x,&y);g_match_info_free(info);
                    a=g_utf8_pointer_to_offset(line.data(),line.data()+x);b=g_utf8_pointer_to_offset(line.data(),line.data()+y);
                } else {a=points.find(q,at);if(a==std::u32string::npos) break;b=a+q.size();}
                if(b>a&&(!word||whole_word(points,a,b))) {
                    out.push_back({path,line,number,int(a+1)});
                    if(out.size()==500) return out;
                    at=b;
                } else at=a+1;
            }
            if(end==text->size()) break;
            start=end+1;
        }
    }
    return out;
}
std::vector<Backlink> Vault::mentions(const std::string& note) const {
    require_note(note);std::vector<Backlink> out;
    if(!utf8_note(*this,note)) return out;
    auto q=lower_points(fs::path(note).stem().string());
    for(auto& path:notes()) if(path!=note) if(auto text=utf8_note(*this,path)) {
        auto mask=prose(*text);
        // Closed frontmatter uses the same line grammar as tag extraction.
        size_t body=0,first=text->find('\n');
        auto line_at=[&](size_t a,size_t b) {auto l=text->substr(a,b-a);if(!l.empty()&&l.back()=='\r') l.pop_back();return l;};
        if(first!=std::string::npos&&line_at(0,first)=="---") for(size_t a=first+1;a<text->size();) {
            auto b=text->find('\n',a);if(b==std::string::npos) b=text->size();
            auto l=line_at(a,b);
            if(l=="---"||l=="...") {body=b<text->size()?b+1:b;break;}a=b+1;
        }
        std::fill(mask.begin(),mask.begin()+body,false);
        for(auto& l:parse_all(*text)) {
            auto a=g_utf8_offset_to_pointer(text->data(),l.offset)-text->data();
            std::fill(mask.begin()+a,mask.begin()+a+l.raw.size(),false);
        }
        int number=0;
        for(size_t start=0;start<=text->size();) {
            auto end=text->find('\n',start);if(end==std::string::npos) end=text->size();
            auto line=line_at(start,end);auto points=lower_points(line);++number;size_t at=0;
            while((at=points.find(q,at))!=std::u32string::npos) {
                auto a=start+(g_utf8_offset_to_pointer(line.data(),at)-line.data());
                auto b=start+(g_utf8_offset_to_pointer(line.data(),at+q.size())-line.data());
                if(whole_word(points,at,at+q.size())&&std::all_of(mask.begin()+a,mask.begin()+b,[](bool b){return b;})) {
                    out.push_back({path,"",line,number,int(at+1)});at+=q.size();
                } else ++at;
            }
            if(end==text->size()) break;
            start=end+1;
        }
    }
    return out;
}
std::vector<Backlink> Vault::backlinks(const std::string& note) const {
    require_note(note);std::vector<Backlink> out;
    if(!utf8_note(*this,note)) return out;
    for(auto& source:notes()) if(source!=note) if(auto text=utf8_note(*this,source)) {
        for(auto& l:all_links(source,*text)) if(l.resolved==Maybe(note)) {
            auto byte=g_utf8_offset_to_pointer(text->data(),l.offset)-text->data();
            auto start=text->rfind('\n',byte);start=start==std::string::npos?0:start+1;
            auto end=text->find('\n',byte);if(end==std::string::npos) end=text->size();
            auto line=text->substr(start,end-start);if(!line.empty()&&line.back()=='\r') line.pop_back();
            out.push_back({source,l.raw,line,l.line,l.col});
        }
    }
    return out;
}
int Rename::map_caret(int offset) const {
    int mapped=offset;
    for(auto& r:rewrites) {
        if(r.end<=offset) mapped+=r.length-(r.end-r.start);
        else if(r.start<offset) mapped-=offset-r.start;
    }
    return mapped;
}
struct Change {std::string path,final,text,original;fs::path staged,backup;bool installed=false;};
// Plan completely before staging. Backups and staged bytes share each original's
// directory, and travel with a directory move. Roll back the namespace first.
static void commit_changes(const Vault& vault,std::vector<Change>& changes,
                           const std::string& old="",const std::string& dest="") {
    auto root=vault.root;
    bool moved=false;std::vector<fs::path> made;
    auto relocate=[&](fs::path p) {
        if(!moved) return p;
        auto rel=p.lexically_relative(root).generic_string();
        if(rel==old||rel.compare(0,old.size()+1,old+"/")==0) return root/(dest+rel.substr(old.size()));
        return p;
    };
    auto cleanup=[&]() {for(auto& c:changes) {
        std::error_code ec;if(!c.staged.empty()) fs::remove(relocate(c.staged),ec);
        if(!c.backup.empty()) fs::remove(relocate(c.backup),ec);
    }};
    auto temporary=[&](const std::string& path,const char* kind) {
        auto parent=(root/path).parent_path();
        for(int i=0;i<1000;++i) {
            auto temp=parent/(".lcos-notes-"+std::string(kind)+"-"+std::to_string(getpid())+"-"+std::to_string(i));
            if(!fs::exists(fs::symlink_status(temp))) return temp;
        }
        fail("cannot allocate temporary path");return fs::path{};
    };
    try {
        for(auto& c:changes) {
            auto backup=temporary(c.path,"backup");
            if(::link((root/c.path).c_str(),backup.c_str())!=0) fail("cannot back up note");
            c.backup=backup;
            auto staged=temporary(c.path,"save");
            FD file(open(staged.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600));c.staged=staged;
            struct stat st{};
            if(stat((root/c.path).c_str(),&st)!=0||fchmod(file.n,st.st_mode&0777)!=0) fail("cannot preserve permissions");
            size_t written=0;
            while(written<c.text.size()) {
                auto n=write(file.n,c.text.data()+written,c.text.size()-written);
                if(n<0&&errno==EINTR) continue;
                if(n<=0) fail("cannot write note");
                written+=n;
            }
            if(fsync(file.n)!=0) fail("cannot flush note");
        }
        for(auto& c:changes) if(utf8_note(vault,c.path)!=Maybe(c.original)) fail("Changed on disk; not renamed");
        if(!old.empty()&&old!=dest) {
            fs::path current=root;
            for(auto& part:fs::path(dest).parent_path()) {current/=part;if(fs::create_directory(current)) made.push_back(current);}
            fs::rename(root/old,root/dest);moved=true;
        }
        for(auto& c:changes) {
            if(::rename(relocate(c.staged).c_str(),(root/c.final).c_str())!=0) fail("cannot replace note");
            c.installed=true;FD dir(parent_fd(vault,c.final));fsync(dir.n);
        }
        cleanup();
    } catch(...) {
        if(moved) {fs::rename(root/dest,root/old);moved=false;}
        for(auto it=changes.rbegin();it!=changes.rend();++it) if(it->installed)
            if(::rename(it->backup.c_str(),(root/it->path).c_str())!=0) fail("rename rollback failed; backup retained");
        cleanup();
        for(auto it=made.rbegin();it!=made.rend();++it) {std::error_code ec;fs::remove(*it,ec);}
        throw;
    }
}
Rename Vault::retag(std::string old,std::string target) const {
    if(!old.empty()&&old[0]=='#') old.erase(0,1);
    if(!target.empty()&&target[0]=='#') target.erase(0,1);
    if(!valid_tag(old)||!valid_tag(target)) fail("invalid tag");
    auto key=fold(old),next=fold(target);
    if(next.compare(0,key.size()+1,key+"/")==0) fail("new tag is nested under old tag");
    Rename result{old,target,{},{},{}};std::vector<Change> changes;bool found=false;
    for(auto& path:notes()) if(auto text=utf8_note(*this,path)) {
        auto rewritten=*text;
        auto occurrences=tag_occurrences(*text);
        for(auto it=occurrences.rbegin();it!=occurrences.rend();++it) {
            auto k=fold(it->tag);
            if(k!=key&&k.compare(0,key.size()+1,key+"/")!=0) continue;
            found=true;
            // Locate the prefix boundary in original bytes, including folds which
            // expand a character and NFC spellings of a component.
            size_t n=it->tag.size();
            if(k!=key) {
                for(size_t slash=it->tag.find('/');slash!=std::string::npos;slash=it->tag.find('/',slash+1))
                    if(fold(it->tag.substr(0,slash))==key) {n=slash;break;}
            }
            if(it->tag.substr(0,n)==target) continue;
            rewritten.replace(it->start,n,target);
            int a=chars(text->substr(0,it->start)),b=a+chars(it->tag.substr(0,n));
            result.note_rewrites[path].push_back({a,b,chars(target)});
        }
        if(rewritten!=*text) {result.updated.push_back(path);changes.push_back({path,path,rewritten,*text,{},{},false});}
    }
    if(!found) fail("old tag occurs nowhere");
    commit_changes(*this,changes);return result;
}
Rename Vault::rename(const std::string& old,std::string target) const {
    auto before=files(),dirs=directories();
    bool folder=std::find(dirs.begin(),dirs.end(),old)!=dirs.end();
    bool note=!folder&&is_note(old);
    if(!folder&&std::find(before.begin(),before.end(),old)==before.end()) fail("source does not exist");
    if(note&&!utf8_note(*this,old)) fail("note is not UTF-8 text");
    auto dest=validated_target(trim(target),note)+(note?".md":"");
    auto moved=[&](const std::string& path) {
        return path==old||(folder&&path.compare(0,old.size()+1,old+"/")==0)?dest+path.substr(old.size()):path;
    };
    if(folder) {
        if(fold(dest).compare(0,fold(old).size()+1,fold(old)+"/")==0) fail("new path is inside old path");
        for(fs::recursive_directory_iterator i(root/old),end;i!=end;++i) {
            if(fs::is_symlink(i->symlink_status())) fail("symlink under moved folder");
            if(fs::is_regular_file(i->symlink_status())&&is_note(i->path().string())) {
                std::ifstream in(i->path(),std::ios::binary);std::string text((std::istreambuf_iterator<char>(in)),{});
                if(!g_utf8_validate(text.data(),text.size(),nullptr)) fail("note is not UTF-8 text");
            }
        }
    }
    auto all=before;all.insert(all.end(),dirs.begin(),dirs.end());
    for(auto& path:all) if(path!=old&&fold(path)==fold(dest)&&(!note||is_note(path)||path==dest)) fail("rename path already exists");
    fs::path current=root;
    for(auto& part:fs::path(dest)) {
        current/=part;auto st=fs::symlink_status(current);
        if(fs::is_symlink(st)) fail("symlink in rename path");
        if(fs::exists(st)&&((current==root/dest&&dest!=old)||(current!=root/dest&&!fs::is_directory(st)))) fail("rename path already exists");
    }
    auto after=before;for(auto& path:after) path=moved(path);std::sort(after.begin(),after.end());
    std::vector<Change> changes;Rename result{old,dest,{},{},{}};
    for(auto& path:notes()) if(auto text=utf8_note(*this,path)) {
        auto source=moved(path);auto rewritten=*text;
        auto links=parse_all(*text);
        for(auto it=links.rbegin();it!=links.rend();++it) {
            auto& l=*it;auto resolved=l.markdown?resolve_markdown(before,path,l.target):resolve_files(before,path,l.target);if(!resolved) continue;
            auto intended=moved(*resolved);
            if((l.markdown?resolve_markdown(after,source,l.target):resolve_files(after,source,l.target))==Maybe(intended)) continue;
            auto full=is_note(intended)?intended.substr(0,intended.size()-3):intended;
            auto name=fs::path(full).filename().string();
            auto canonical=[&](const std::string& t) -> Maybe {
                auto raw=std::string(l.embed?"![[":"[[")+t+(l.heading?"#"+*l.heading:"")+(l.alias?"|"+*l.alias:"")+"]]";
                auto check=parse(raw);
                if(check.size()==1&&check[0].raw==raw&&check[0].heading==l.heading&&check[0].alias==l.alias&&resolve_files(after,source,check[0].target)==Maybe(intended)) return raw;
                return {};
            };
            Maybe raw;
            if(l.markdown) {
                auto newpath=l.target.compare(0,1,"/")==0 ? "/"+intended : fs::path(intended).lexically_relative(directory(source).empty()?fs::path("."):fs::path(directory(source))).generic_string();
                if(is_note(intended)&&strip(l.target)==l.target) newpath=strip(newpath);
                auto encode=[&](const std::string& s,bool path) {
                    std::string out;const char* hex="0123456789ABCDEF";
                    for(unsigned char c:s) {
                        if(c=='%'||(path&&c=='#')||(!l.angle&&std::strchr(" ()<>",c)!=nullptr)) {out+='%';out+=hex[c>>4];out+=hex[c&15];}
                        else out+=c;
                    }
                    return out;
                };
                auto dest=encode(newpath,true)+(l.heading?"#"+encode(*l.heading,false):"");
                auto candidate="["+l.text+"]("+(l.angle?"<":"")+dest+(l.angle?">":"")+")";
                auto check=parse_markdown(candidate);
                if(check.size()==1&&check[0].raw==candidate&&check[0].text==l.text&&check[0].heading==l.heading&&resolve_markdown(after,source,check[0].target)==Maybe(intended)) raw=candidate;
            } else {raw=canonical(name);if(!raw) raw=canonical(full);}
            if(!raw) fail("link cannot preserve its destination");
            auto begin=g_utf8_offset_to_pointer(text->data(),l.offset)-text->data();
            rewritten.replace(begin,l.raw.size(),*raw);
            result.note_rewrites[path].push_back({l.offset,l.offset+l.length,int(g_utf8_strlen(raw->data(),raw->size()))});
        }
        // A new destination containing Markdown punctuation can change the prose
        // mask around it. Verify the final document before staging any writes.
        auto final_links=parse_all(rewritten);
        if(final_links.size()!=links.size()) fail("link cannot preserve its destination in document");
        for(size_t i=0;i<links.size();++i) {
            const auto& l=links[i];const auto& next=final_links[i];
            auto was=l.markdown?resolve_markdown(before,path,l.target):resolve_files(before,path,l.target);
            auto now=next.markdown?resolve_markdown(after,source,next.target):resolve_files(after,source,next.target);
            if(l.markdown!=next.markdown || (was ? now!=Maybe(moved(*was)) : next.raw!=l.raw))
                fail("link cannot preserve its destination in document");
        }
        if(rewritten!=*text) result.updated.push_back(source);
        if(rewritten!=*text) changes.push_back({path,source,rewritten,*text,{},{},false});
    }
    std::sort(result.updated.begin(),result.updated.end());
    if(dest==old&&result.updated.empty()) return result;
    if(result.note_rewrites.count(old)) result.rewrites=result.note_rewrites.at(old);
    commit_changes(*this,changes,old,dest);
    return result;
}


}
