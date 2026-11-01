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
    std::unique_ptr<char, decltype(&g_free)> p(g_utf8_casefold(s.data(), s.size()), g_free);
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
static int parent_fd(const Vault& v,const std::string& path) {
    int fd=open(v.root.c_str(),O_RDONLY|O_DIRECTORY|O_CLOEXEC);
    if(fd<0) fail("cannot open vault");
    for(auto& part:fs::path(path).parent_path()) {
        auto s=part.string();
        if(s.empty()||s[0]=='.') {close(fd);fail("unsafe directory");}
        int next=openat(fd,s.c_str(),O_RDONLY|O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC);
        close(fd); if(next<0) fail("unsafe or missing directory"); fd=next;
    }
    return fd;
}
static std::string validated_target(std::string target) {
    target=strip(target);
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
    stamp=after; original=bytes; text=bytes; path=relative;
}
void Document::save(const Vault& vault,const std::string& contents) {
    if(contents==original) {text=contents;return;}
    FD dir(parent_fd(vault,path)); auto name=fs::path(path).filename().string();
    auto unchanged=[&]() {
        int n=openat(dir.n,name.c_str(),O_RDONLY|O_NOFOLLOW|O_CLOEXEC);
        if(n<0) return false;
        FD file(n); struct stat st{};
        return fstat(file.n,&st)==0 && same(st,stamp) && read_fd(file.n)==original;
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
        original=contents; text=contents;
    } catch(...) {unlinkat(dir.n,temp.c_str(),0);throw;}
}
int heading_offset(const std::string& text,const std::string& heading) {
    if(heading.empty() || heading[0]=='^') return 0;
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
static std::string whitespace(std::string s) {
    auto a=s.find_first_not_of(" \t\r\n");if(a==std::string::npos) return "";
    return s.substr(a,s.find_last_not_of(" \t\r\n")-a+1);
}
static std::vector<std::string> note_tags(const std::string& text) {
    std::vector<std::string> out,lines;
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
    auto item=[&](std::string s) {
        s=whitespace(s);
        if(s.size()>=2&&((s.front()=='\''&&s.back()=='\'')||(s.front()=='"'&&s.back()=='"'))) s=s.substr(1,s.size()-2);
        if(!s.empty()&&s[0]=='#') s.erase(0,1);
        if(valid_tag(s)) out.push_back(s);
    };
    for(size_t i=1;i<finish;++i) if(lines[i].compare(0,5,"tags:")==0) {
        auto s=whitespace(lines[i].substr(5));
        if(s.empty()) {
            while(i+1<finish) {
                auto next=lines[i+1];auto at=next.find_first_not_of(" \t");
                if(at==std::string::npos||next.compare(at,2,"- ")!=0) break;
                ++i;item(next.substr(at+2));
            }
        } else if(s.front()=='[') {
            if(s.back()!=']') continue;
            s=s.substr(1,s.size()-2);size_t start=0;
            for(size_t j=0;j<=s.size();++j) {
                if(j==s.size()||s[j]==',') {item(s.substr(start,j-start));start=j+1;}
            }
        } else {
            size_t start=0;
            for(size_t j=0;j<=s.size();++j) if(j==s.size()||s[j]==','||g_ascii_isspace(s[j])) {item(s.substr(start,j-start));start=j+1;}
        }
    }
    auto mask=prose(text);
    for(size_t n=body;n<lines.size();++n) {
        const auto& line=lines[n];
        for(size_t i=0;i<line.size();++i) {
            if(line[i]!='#'||!mask[starts[n]+i]||(i&&line[i-1]!=' '&&line[i-1]!='\t')) continue;
            size_t j=i+1;
            while(j<line.size()&&tag_char(g_utf8_get_char(line.data()+j))) j=g_utf8_next_char(line.data()+j)-line.data();
            auto tag=line.substr(i+1,j-i-1);if(valid_tag(tag)) out.push_back(tag);
            i=j?j-1:i;
        }
    }
    return out;
}
std::vector<Tag> Vault::tags() const {
    std::map<std::string,Tag> all;
    for(auto& path:notes()) if(auto text=utf8_note(*this,path)) {
        std::set<std::string> seen;
        for(auto& tag:note_tags(*text)) {
            auto key=fold(tag);if(!seen.insert(key).second) continue;
            auto& row=all[key];if(row.count==0) row.tag=tag;++row.count;
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
std::vector<Match> Vault::find(const std::string& query) const {
    if(query.empty()) fail("empty query");
    auto q=lower_points(query);std::vector<Match> out;
    for(auto& path:notes()) if(auto text=utf8_note(*this,path)) {
        int number=0;
        for(size_t start=0;start<=text->size();) {
            auto end=text->find('\n',start);if(end==std::string::npos) end=text->size();
            auto line=text->substr(start,end-start);if(!line.empty()&&line.back()=='\r') line.pop_back();
            ++number;auto points=lower_points(line);size_t at=0;
            while((at=points.find(q,at))!=std::u32string::npos) {
                out.push_back({path,line,number,int(at+1)});
                if(out.size()==500) return out;
                at+=q.size();
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
    auto all=files();
    for(auto& source:notes()) if(source!=note) if(auto text=utf8_note(*this,source)) {
        for(auto& l:parse(*text)) if(resolve_files(all,source,l.target)==Maybe(note)) {
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
Rename Vault::rename(const std::string& old,std::string target) const {
    require_note(old);if(!utf8_note(*this,old)) fail("note is not UTF-8 text");
    auto dest=validated_target(trim(target))+".md";
    auto before=files(),after=before;
    for(auto& path:before) if(path!=old&&is_note(path)&&fold(path)==fold(dest)) fail("note already exists");
    fs::path current=root;
    for(auto& part:fs::path(dest)) {
        current/=part;auto st=fs::symlink_status(current);
        if(fs::is_symlink(st)) fail("symlink in rename path");
        if(fs::exists(st)&&((current==root/dest&&dest!=old)|| (current!=root/dest&&!fs::is_directory(st)))) fail("rename path already exists");
    }
    *std::find(after.begin(),after.end(),old)=dest;std::sort(after.begin(),after.end());
    struct Change {std::string path,final,text,original;fs::path staged,backup;bool installed=false;};
    std::vector<Change> changes;Rename result{old,dest,{},{}};
    for(auto& path:notes()) if(auto text=utf8_note(*this,path)) {
        auto source=path==old?dest:path;auto rewritten=*text;
        auto links=parse(*text);
        for(auto it=links.rbegin();it!=links.rend();++it) {
            auto& l=*it;auto resolved=resolve_files(before,path,l.target);if(!resolved) continue;
            auto intended=*resolved==old?dest:*resolved;
            if(resolve_files(after,source,l.target)==Maybe(intended)) continue;
            auto full=is_note(intended)?intended.substr(0,intended.size()-3):intended;
            auto name=fs::path(full).filename().string();
            auto canonical=[&](const std::string& t) -> Maybe {
                auto raw=std::string(l.embed?"![[":"[[")+t+(l.heading?"#"+*l.heading:"")+(l.alias?"|"+*l.alias:"")+"]]";
                auto check=parse(raw);
                if(check.size()==1&&check[0].raw==raw&&check[0].heading==l.heading&&check[0].alias==l.alias&&resolve_files(after,source,check[0].target)==Maybe(intended)) return raw;
                return {};
            };
            auto raw=canonical(name);if(!raw) raw=canonical(full);
            if(!raw) fail("link cannot preserve its destination");
            auto begin=g_utf8_offset_to_pointer(text->data(),l.offset)-text->data();
            rewritten.replace(begin,l.raw.size(),*raw);
            if(path==old) result.rewrites.push_back({l.offset,l.offset+l.length,int(g_utf8_strlen(raw->data(),raw->size()))});
        }
        if(rewritten!=*text) result.updated.push_back(source);
        if(rewritten!=*text||path==old) changes.push_back({path,source,rewritten,*text,{},{},false});
    }
    std::sort(result.updated.begin(),result.updated.end());
    if(dest==old&&result.updated.empty()) return result;
    // Stage every changed file before replacing any original. Hard-link backups allow
    // rollback of an I/O failure during the multi-file commit. Untouched files are moved.
    std::vector<fs::path> made;
    auto cleanup=[&]() {for(auto& c:changes) {std::error_code ec;if(!c.staged.empty()) fs::remove(c.staged,ec);if(!c.backup.empty()) fs::remove(c.backup,ec);}};
    auto temporary=[&](const std::string& path,const char* kind) {
        auto parent=(root/path).parent_path();
        for(int i=0;i<1000;++i) {
            auto temp=parent/(".lcos-notes-"+std::string(kind)+"-"+std::to_string(getpid())+"-"+std::to_string(i));
            if(!fs::exists(fs::symlink_status(temp))) return temp;
        }
        fail("cannot allocate temporary path");return fs::path{};
    };
    try {
        current=root;
        for(auto& part:fs::path(dest).parent_path()) {current/=part;if(fs::create_directory(current)) made.push_back(current);}
        for(auto& c:changes) {
            auto backup=temporary(c.path,"backup");
            if(::link((root/c.path).c_str(),backup.c_str())!=0) fail("cannot back up note");
            c.backup=backup;
            if(c.text==c.original) continue;
            auto staged=temporary(c.final,"save");
            FD file(open(staged.c_str(),O_WRONLY|O_CREAT|O_EXCL|O_NOFOLLOW|O_CLOEXEC,0600));
            c.staged=staged;
            struct stat st{};if(stat((root/c.path).c_str(),&st)!=0||fchmod(file.n,st.st_mode&0777)!=0) fail("cannot preserve permissions");
            size_t written=0;
            while(written<c.text.size()) {auto n=write(file.n,c.text.data()+written,c.text.size()-written);if(n<0&&errno==EINTR) continue;if(n<=0) fail("cannot write note");written+=n;}
            if(fsync(file.n)!=0) fail("cannot flush note");
        }
        for(auto& c:changes) if(utf8_note(*this,c.path)!=Maybe(c.original)) fail("Changed on disk; not renamed");
        for(auto& c:changes) {
            auto from=c.staged.empty()?root/c.path:c.staged;
            if(::rename(from.c_str(),(root/c.final).c_str())!=0) fail("cannot replace note");
            c.installed=true;
            if(c.path!=c.final&&!c.staged.empty()&&::unlink((root/c.path).c_str())!=0) fail("cannot remove old note");
            FD dir(parent_fd(*this,c.final));fsync(dir.n);
        }
        cleanup();
    } catch(...) {
        for(auto it=changes.rbegin();it!=changes.rend();++it) if(it->installed) {
            if(it->path!=it->final) ::unlink((root/it->final).c_str());
            if(::rename(it->backup.c_str(),(root/it->path).c_str())!=0) fail("rename rollback failed; backup retained");
        }
        cleanup();for(auto it=made.rbegin();it!=made.rend();++it) {std::error_code ec;fs::remove(*it,ec);}throw;
    }
    return result;
}


}
