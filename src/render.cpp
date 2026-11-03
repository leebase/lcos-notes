// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Lee Harrington
#include "core.hpp"
#include <cmark-gfm.h>
#include <cmark-gfm-core-extensions.h>
#include <glib.h>
#include <algorithm>
#include <map>
#include <functional>
#include <memory>
#include <regex>
#include <set>
#include <stdexcept>
#include <tuple>

namespace notes {
namespace {
int count(const std::string& s) { return g_utf8_strlen(s.data(), s.size()); }
std::string utf8(gunichar c) { char b[6]; auto n=g_unichar_to_utf8(c,b);return std::string(b,n); }
void append(Render& out, Render part) {
    int offset=count(out.text);out.text+=part.text;
    for(auto image:part.images) {image.offset+=offset;out.images.push_back(image);}
    for(auto t:part.tasks) {t.offset+=offset;out.tasks.push_back(t);}
    for(auto b:part.blocks) {b.offset+=offset;out.blocks.push_back(b);}
    for(auto s:part.spans) {s.start+=offset;s.end+=offset;out.spans.push_back(s);}
    for(auto s:part.layout_spans) {s.start+=offset;s.end+=offset;out.layout_spans.push_back(s);}
    for(auto l:part.links) {l.start+=offset;l.end+=offset;out.links.push_back(l);}
}
void style(Render& r,const std::string& name) {
    Span span{0,count(r.text),name};r.spans.push_back(span);
    if(name=="embed"||name=="quote") r.layout_spans.push_back(span);
}
std::string literal(cmark_node* n) {auto s=cmark_node_get_literal(n);return s?s:"";}
// cmark recognizes LF, CRLF and lone CR, but not Unicode paragraph separators.
std::vector<size_t> line_starts(const std::string& text) {
    std::vector<size_t> starts{0};
    for(size_t i=0;i<text.size();++i) {
        if(text[i]=='\r') {
            if(i+1<text.size()&&text[i+1]=='\n') ++i;
            starts.push_back(i+1);
        } else if(text[i]=='\n') starts.push_back(i+1);
    }
    return starts;
}
thread_local std::vector<std::string> embed_stack;
struct Renderer {
    const Vault* vault=nullptr;
    std::map<gunichar,Link> tokens;
    std::string source_name, source_path;
    std::string source, parsed;
    std::vector<size_t> source_lines, parsed_lines, source_offsets;
    int removed=0, parser_removed=0;
    Task task(cmark_node* item) const {
        int body_line=cmark_node_get_start_line(item);
        int line=body_line+parser_removed;
        auto start=parsed_lines.at(line-1);
        auto end=line<int(parsed_lines.size())?parsed_lines[line]:parsed.size();
        auto pos=parsed.find('[',start+std::max(0,cmark_node_get_start_column(item)-1));
        if(pos==std::string::npos||pos+2>=end) throw std::runtime_error("cannot locate task marker");
        auto original=source_offsets.at(pos);
        auto source_line=std::upper_bound(source_lines.begin(),source_lines.end(),original)-source_lines.begin();
        return {body_line+removed,count(source.substr(source_lines[source_line-1],original-source_lines[source_line-1]))+1,
                source[original+1]=='x'||source[original+1]=='X',0,original+1};
    }
    Render expand(const std::string& text,bool raw) const {
        Render r;
        for(const char* p=text.data();p<text.data()+text.size();p=g_utf8_next_char(p)) {
            auto c=g_utf8_get_char(p);auto found=tokens.find(c);
            if(found==tokens.end()) {r.text+=utf8(c);continue;}
            auto& l=found->second;
            if(raw) {r.text+=l.raw;continue;}
            std::string display;
            if(l.markdown) {
                if(!l.text.empty()) display=l.text;
                else {
                    auto path=l.resolved?*l.resolved:l.target;
                    display=fs::path(path).filename().string();
                    if(display.empty()) display=source_name;
                    // Compare the ASCII suffix without slicing through a UTF-8 character.
                    else if(display.size()>=3&&display[display.size()-3]=='.'&&
                            (display[display.size()-2]=='m'||display[display.size()-2]=='M')&&
                            (display.back()=='d'||display.back()=='D')) display.resize(display.size()-3);
                }
            }
            else if(l.alias&&!l.alias->empty()) display=*l.alias;
            else if(l.heading&&!l.heading->empty()) display=(l.target.empty()?"":l.target+" > ")+*l.heading;
            else display=l.target.empty()?source_name:l.target;
            int start=count(r.text);r.text+=display;int end=count(r.text);
            r.spans.push_back({start,end,l.resolved?"link":"unresolved"});
            r.links.push_back({start,end,l.raw,l.resolved,source_path});
        }
        return r;
    }
    Render text_run(const std::string& text) const {
        std::vector<gunichar> chars;
        for(const char* p=text.data();p<text.data()+text.size();p=g_utf8_next_char(p)) chars.push_back(g_utf8_get_char(p));
        auto slice=[&](size_t a,size_t b) {std::string s;for(;a<b;++a) s+=utf8(chars[a]);return s;};
        Render r;size_t plain=0,i=0;
        while(i+2<chars.size()) {
            if(chars[i]!='='||chars[i+1]!='='||chars[i+2]=='='||g_unichar_isspace(chars[i+2])) {++i;continue;}
            size_t j=i+3;
            while(j+1<chars.size()&&!(chars[j]=='='&&chars[j+1]=='='&&!g_unichar_isspace(chars[j-1]))) ++j;
            if(j+1>=chars.size()) {++i;continue;}
            append(r,expand(slice(plain,i),false));
            auto part=expand(slice(i+2,j),false);style(part,"highlight");append(r,std::move(part));
            i=j+2;plain=i;
        }
        append(r,expand(slice(plain,chars.size()),false));return r;
    }
    Render inline_range(cmark_node* c,cmark_node* stop=nullptr) const {
        Render r;
        while(c && c!=stop) {
            if(cmark_node_get_type(c)==CMARK_NODE_TEXT) {
                std::string run;
                do {run+=literal(c);c=cmark_node_next(c);} while(c&&c!=stop&&cmark_node_get_type(c)==CMARK_NODE_TEXT);
                append(r,text_run(run));
            } else {append(r,inline_node(c));c=cmark_node_next(c);}
        }
        return r;
    }
    Render inlines(cmark_node* n) const {return inline_range(cmark_node_first_child(n));}
    Render inline_node(cmark_node* n) const {
        auto type=cmark_node_get_type(n);Render r;
        switch(type) {
        case CMARK_NODE_TEXT:return expand(literal(n),false);
        case CMARK_NODE_SOFTBREAK:r.text=" ";return r;
        case CMARK_NODE_LINEBREAK:r.text="\n";return r;
        case CMARK_NODE_CODE:r=expand(literal(n),true);style(r,"code");return r;
        case CMARK_NODE_HTML_INLINE:return expand(literal(n),true);
        default:r=inlines(n);break;
        }
        if(std::string(cmark_node_get_type_string(n))=="strikethrough") style(r,"strike");
        if(type==CMARK_NODE_EMPH) style(r,"em");
        if(type==CMARK_NODE_STRONG) style(r,"strong");
        if(type==CMARK_NODE_LINK||type==CMARK_NODE_IMAGE) style(r,"url");
        return r;
    }
    Render blocks(cmark_node* n,const std::string& sep) const {
        Render r;bool first=true;
        for(auto c=cmark_node_first_child(n);c;c=cmark_node_next(c)) {
            if(!first) r.text+=sep;
            first=false;append(r,block(c));
        }
        return r;
    }
    static Render indent(Render r,const std::string& prefix) {
        // Boundaries have different affinity: a start at a line boundary is
        // after its padding, while an end at that boundary is before it.
        std::vector<int> inserts{0};std::string text=prefix;int pos=0;
        for(const char* p=r.text.data();p<r.text.data()+r.text.size();p=g_utf8_next_char(p)) {
            auto c=g_utf8_get_char(p);text+=utf8(c);++pos;
            auto next=g_utf8_next_char(p);
            if(c=='\n'&&next<r.text.data()+r.text.size()&&*next!='\n') {
                inserts.push_back(pos);text+=std::string(count(prefix),' ');
            }
        }
        int width=count(prefix);
        auto start=[&](int o) {return o+width*(std::upper_bound(inserts.begin(),inserts.end(),o)-inserts.begin());};
        auto end=[&](int o) {return o+width*(std::lower_bound(inserts.begin(),inserts.end(),o)-inserts.begin());};
        for(auto& image:r.images) image.offset=start(image.offset);
        for(auto& t:r.tasks) t.offset=start(t.offset);
        for(auto& b:r.blocks) b.offset=start(b.offset);
        for(auto& s:r.spans) {s.start=start(s.start);s.end=end(s.end);}
        for(auto& s:r.layout_spans) {s.start=start(s.start);s.end=end(s.end);}
        for(auto& l:r.links) {l.start=start(l.start);l.end=end(l.end);}
        r.text=std::move(text);return r;
    }
    void strip_block_id(Render& r,cmark_node* last) const {
        if(!last||cmark_node_get_type(last)!=CMARK_NODE_TEXT) return;
        auto text=literal(last);size_t id=text.size();
        while(id>0&&(g_ascii_isalnum(text[id-1])||text[id-1]=='-')) --id;
        if(id==text.size()||id==0||text[id-1]!='^') return;
        size_t a=id-1;while(a>0&&(text[a-1]==' '||text[a-1]=='\t')) --a;
        if(a==id-1) return;
        int limit=count(r.text)-count(text.substr(a));
        if(limit<0) return;
        r.text.resize(g_utf8_offset_to_pointer(r.text.data(),limit)-r.text.data());
        for(auto& span:r.spans) span.end=std::min(span.end,limit);
        for(auto& link:r.links) link.end=std::min(link.end,limit);
        r.links.erase(std::remove_if(r.links.begin(),r.links.end(),[](const RenderLink& l){return l.start>=l.end;}),r.links.end());
    }
    Render block(cmark_node* n) const {
        auto r=block_contents(n);
        if(cmark_node_get_type(n)!=CMARK_NODE_LIST)
            r.blocks.insert(r.blocks.begin(),{cmark_node_get_start_line(n),0});
        return r;
    }
    Render block_contents(cmark_node* n) const {
        Render r;auto type=cmark_node_get_type(n);
        if(std::string(cmark_node_get_type_string(n))=="table") {
            std::vector<std::vector<Render>> rows;
            std::vector<int> widths(cmark_gfm_extensions_get_table_columns(n),1);
            for(auto row=cmark_node_first_child(n);row;row=cmark_node_next(row)) {
                std::vector<Render> cells;size_t col=0;
                for(auto cell=cmark_node_first_child(row);cell;cell=cmark_node_next(cell),++col) {
                    auto part=inlines(cell);widths.at(col)=std::max(widths.at(col),count(part.text));cells.push_back(std::move(part));
                }
                rows.push_back(std::move(cells));
            }
            auto align=cmark_gfm_extensions_get_table_alignments(n);size_t index=0;
            for(auto row=cmark_node_first_child(n);row;row=cmark_node_next(row),++index) {
                if(index) r.text+='\n';
                r.blocks.push_back({cmark_node_get_start_line(row),count(r.text)});
                for(size_t col=0;col<widths.size();++col) {
                    if(col) r.text+=" │ ";
                    auto part=rows[index][col];int pad=widths[col]-count(part.text);
                    int left=align[col]=='r'?pad:align[col]=='c'?pad/2:0;
                    r.text+=std::string(left,' ');
                    if(!index) style(part,"th");
                    append(r,std::move(part));r.text+=std::string(pad-left,' ');
                }
                if(!index) {
                    r.text+='\n';
                    for(size_t col=0;col<widths.size();++col) {
                        if(col) r.text+="─┼─";
                        for(int i=0;i<widths[col];++i) r.text+="─";
                    }
                }
            }
            style(r,"table");return r;
        }
        switch(type) {
        case CMARK_NODE_PARAGRAPH: {
            auto only=cmark_node_first_child(n);
            if(only&&!cmark_node_next(only)&&cmark_node_get_type(only)==CMARK_NODE_TEXT) {
                auto value=literal(only);
                auto first=value.find_first_not_of(" \t\r\n");
                value=first==std::string::npos?"":value.substr(first,value.find_last_not_of(" \t\r\n")-first+1);
                if(g_utf8_strlen(value.c_str(),value.size())==1) {
                    auto it=tokens.find(g_utf8_get_char(value.c_str()));
                    if(it!=tokens.end()&&it->second.embed&&!it->second.markdown&&it->second.resolved) {
                        auto path=*it->second.resolved;auto ext=fs::path(path).extension().string();
                        std::transform(ext.begin(),ext.end(),ext.begin(),[](unsigned char c){return g_ascii_tolower(c);});
                        if(ext==".png"||ext==".jpg"||ext==".jpeg"||ext==".gif"||ext==".bmp"||ext==".webp") {
                            r.text="\xEF\xBF\xBC";style(r,"image");r.images.push_back({0,path});return r;
                        }
                        if(is_note(path)&&embed_stack.size()<4&&
                           std::find(embed_stack.begin(),embed_stack.end(),path)==embed_stack.end()) {
                            try {
                                Document doc;doc.load(*vault,path);
                                auto part=vault->render(path,doc.text,it->second.heading.value_or(""));
                                if(!part.text.empty()) {
                                    part.blocks.clear();part.tasks.clear();
                                    part.spans.erase(std::remove_if(part.spans.begin(),part.spans.end(),[](const Span& s){return s.style=="task";}),part.spans.end());
                                    style(part,"embed");return part;
                                }
                            } catch(const std::exception&) {}
                        }
                    }
                }
            }
            r=inlines(n);
            auto last=cmark_node_last_child(n);
            if(last&&cmark_node_get_type(last)==CMARK_NODE_TEXT) {
                auto text=literal(last);size_t end=text.size(),id=end;
                while(id>0&&(g_ascii_isalnum(text[id-1])||text[id-1]=='-')) --id;
                if(id<end&&id>0&&text[id-1]=='^') {
                    size_t a=id-1;
                    while(a>0&&(text[a-1]==' '||text[a-1]=='	')) --a;
                    if(a<id-1) {
                        auto suffix=count(text.substr(a));
                        int limit=count(r.text)-suffix;
                        r.text.resize(g_utf8_offset_to_pointer(r.text.data(),limit)-r.text.data());
                        for(auto& s:r.spans) s.end=std::min(s.end,limit);
                        for(auto& l:r.links) l.end=std::min(l.end,limit);
                        r.links.erase(std::remove_if(r.links.begin(),r.links.end(),[](auto& l){return l.start>=l.end;}),r.links.end());
                    }
                }
            }
            return r;
        }
        case CMARK_NODE_HEADING:r=inlines(n);style(r,"h"+std::to_string(cmark_node_get_heading_level(n)));return r;
        case CMARK_NODE_CODE_BLOCK:
        case CMARK_NODE_HTML_BLOCK: {
            auto s=literal(n);if(!s.empty()&&s.back()=='\n') s.pop_back();r=expand(s,true);
            if(type==CMARK_NODE_CODE_BLOCK) style(r,"codeblock");
            return r;
        }
        case CMARK_NODE_THEMATIC_BREAK:
            for(int i=0;i<20;++i) r.text+="─";
            style(r,"rule");return r;
        case CMARK_NODE_BLOCK_QUOTE: {
            auto para=cmark_node_first_child(n);
            if(para&&cmark_node_get_type(para)==CMARK_NODE_PARAGRAPH) {
                auto br=cmark_node_first_child(para);
                while(br&&cmark_node_get_type(br)!=CMARK_NODE_SOFTBREAK&&cmark_node_get_type(br)!=CMARK_NODE_LINEBREAK) br=cmark_node_next(br);
                auto head=inline_range(cmark_node_first_child(para),br);
                if(!br) strip_block_id(head,cmark_node_last_child(para));
                // Parse the ASCII marker without recursive regex matching. The title
                // uses Python's non-DOTALL semantics: CR is allowed, LF is not.
                const auto& h=head.text;
                size_t pos=0, type_start=2, type_end=0, marker_end=0, title_start=0;
                char sign=0;bool has_title=false, matched=false;
                if(h.size()>=3&&h[0]=='['&&h[1]=='!') {
                    pos=2;
                    while(pos<h.size()&&((h[pos]>='A'&&h[pos]<='Z')||(h[pos]>='a'&&h[pos]<='z')||
                          (h[pos]>='0'&&h[pos]<='9')||h[pos]=='_'||h[pos]=='-')) ++pos;
                    type_end=pos;
                    if(pos>type_start&&pos<h.size()&&h[pos]==']') {
                        ++pos;
                        if(pos<h.size()&&(h[pos]=='+'||h[pos]=='-')) sign=h[pos++];
                        marker_end=pos;
                        if(pos<h.size()&&(h[pos]==' '||h[pos]=='\t')) {
                            has_title=true;
                            while(pos<h.size()&&(h[pos]==' '||h[pos]=='\t')) ++pos;
                            title_start=pos;pos=h.size();
                        }
                        matched=pos==h.size()&&h.find('\n')==std::string::npos;
                    }
                }
                if(matched) {
                    int marker=count(h.substr(0,marker_end));
                    bool valid=true;
                    for(auto& span:head.spans) if(span.start<marker) valid=false;
                    for(auto& link:head.links) if(link.start<marker) valid=false;
                    if(valid) {
                        std::string type=h.substr(type_start,type_end-type_start),kind=type;
                        std::transform(kind.begin(),kind.end(),kind.begin(),[](unsigned char c){return g_ascii_tolower(c);});
                        if(kind!="note"&&kind!="tip"&&kind!="warning"&&kind!="danger"&&kind!="question"&&kind!="quote") kind="note";
                        Render title;
                        if(has_title&&title_start<h.size()) {
                            int shift=count(h.substr(0,title_start));
                            title.text=h.substr(title_start);
                            for(auto span:head.spans) if(span.end>shift) {span.start=std::max(0,span.start-shift);span.end-=shift;title.spans.push_back(span);}
                            for(auto link:head.links) if(link.end>shift) {link.start=std::max(0,link.start-shift);link.end-=shift;title.links.push_back(link);}
                        } else {
                            std::transform(type.begin(),type.end(),type.begin(),[](unsigned char c){return g_ascii_tolower(c);});
                            type[0]=g_ascii_toupper(type[0]);title.text=type;
                        }
                        style(title,"callout-title");append(r,std::move(title));int title_end=count(r.text);
                        r.blocks.push_back({cmark_node_get_start_line(para),0});
                        if(br) {
                            auto body=inline_range(cmark_node_next(br));
                            strip_block_id(body,cmark_node_last_child(para));
                            if(!body.text.empty()) {r.text+='\n';append(r,std::move(body));}
                        }
                        for(auto child=cmark_node_next(para);child;child=cmark_node_next(child)) {
                            r.text+=count(r.text)==title_end?"\n":"\n\n";append(r,block(child));
                        }
                        if(sign=='-'&&count(r.text)>title_end) r.spans.push_back({title_end,count(r.text),"folded"});
                        style(r,"callout-"+kind);return r;
                    }
                }
            }
            r=blocks(n,"\n\n");style(r,"quote");return r;
        }
        case CMARK_NODE_LIST: {
            int index=cmark_node_get_list_start(n);bool first=true;
            for(auto item=cmark_node_first_child(n);item;item=cmark_node_next(item),++index) {
                auto prefix=cmark_node_get_list_type(n)==CMARK_ORDERED_LIST?
                    std::to_string(index)+(cmark_node_get_list_delim(n)==CMARK_PAREN_DELIM?") ":". "):"• ";
                bool is_task=std::string(cmark_node_get_type_string(item))=="tasklist";
                Task record{};
                if(is_task) {record=task(item);prefix=cmark_node_get_list_type(n)==CMARK_ORDERED_LIST?prefix:"";prefix+=record.checked?"☑ ":"☐ ";}
                Render children;bool first_child=true;
                for(auto child=cmark_node_first_child(item);child;child=cmark_node_next(child)) {
                    if(!first_child) children.text+=cmark_node_get_list_tight(n)?"\n":"\n\n";
                    auto content=block(child);
                    if(first_child&&is_task&&record.checked) style(content,"done");
                    append(children,std::move(content));first_child=false;
                }
                auto part=indent(std::move(children),prefix);
                if(is_task) {
                    record.offset=count(prefix)-2;
                    part.spans.push_back({record.offset,record.offset+1,"task"});
                    part.tasks.insert(part.tasks.begin(),record);
                }
                part.blocks.insert(part.blocks.begin(),{cmark_node_get_start_line(item),0});
                if(!first) r.text+='\n';
                first=false;append(r,std::move(part));
            }
            return r;
        }
        default:return r;
        }
    }
};
// The frontmatter grammar is shared with U2: only a closed first-line block.
size_t body_start(const std::string& text) {
    auto line=[&](size_t a,size_t b) {auto s=text.substr(a,b-a);if(!s.empty()&&s.back()=='\r') s.pop_back();return s;};
    auto first=text.find('\n');if(first==std::string::npos||line(0,first)!="---") return 0;
    for(size_t a=first+1;a<text.size();) {
        auto b=text.find('\n',a);if(b==std::string::npos) b=text.size();auto s=line(a,b);
        if(s=="---"||s=="...") return b<text.size()?b+1:b;
        a=b+1;
    }
    return 0;
}
}
Render Vault::render(const std::string& source,const std::string& text,const std::string& selection) const {
    if(!g_utf8_validate(text.data(),text.size(),nullptr)) throw std::runtime_error("note is not UTF-8 text");
    struct StackGuard { StackGuard(const std::string& p) {embed_stack.push_back(p);} ~StackGuard() {embed_stack.pop_back();} } guard(source);
    Renderer renderer;renderer.vault=this;renderer.source_path=source;renderer.source_name=fs::path(source).stem().string();
    auto found=all_links(source,text);std::string replaced;size_t cursor=0;
    // Keep parser byte coordinates tied to the original bytes even when a link
    // is replaced by a private-use token of a different encoded length.
    auto copy=[&](size_t end) {
        replaced.append(text,cursor,end-cursor);
        for(;cursor<end;++cursor) renderer.source_offsets.push_back(cursor);
    };
    // Allocate ordinary Unicode private-use characters absent from the input,
    // so literal Unicode in arbitrary documents never becomes an accidental link.
    std::set<gunichar> used;
    for(const char* p=text.data();p<text.data()+text.size();p=g_utf8_next_char(p)) used.insert(g_utf8_get_char(p));
    // Numeric character references can introduce private-use characters during
    // parsing even when those characters were absent from the original bytes.
    // Reserve their values too; named CommonMark entities contain no private use.
    for(size_t i=0;(i=text.find("&#",i))!=std::string::npos;++i) {
        size_t j=i+2;unsigned base=10;
        if(j<text.size()&&(text[j]=='x'||text[j]=='X')) {base=16;++j;}
        gunichar value=0;bool any=false;
        for(;j<text.size();++j) {
            int digit=g_ascii_xdigit_value(text[j]);
            if(digit<0||unsigned(digit)>=base) break;
            any=true;value=value*base+digit;
            if(value>0x10FFFF) break;
        }
        if(any&&value<=0x10FFFF) used.insert(value);
    }
    gunichar token=0xF0000;
    for(auto& l:found) {
        while(used.count(token)||token==0xFFFFE||token==0xFFFFF) ++token;
        if(token>0x10FFFD) throw std::runtime_error("too many wikilinks to render");
        auto byte=size_t(g_utf8_offset_to_pointer(text.data(),l.offset)-text.data());
        copy(byte);auto placeholder=utf8(token);replaced+=placeholder;
        for(size_t i=0;i<placeholder.size();++i) renderer.source_offsets.push_back(byte);
        renderer.tokens.emplace(token++,l);cursor=byte+l.raw.size();
    }
    copy(text.size());renderer.source_offsets.push_back(text.size());
    auto start=body_start(replaced);
    // Public coordinates inherit the LF-based frontmatter grammar. Parser
    // lookup must also count lone CRs, without adding them to reported lines.
    int removed=std::count(replaced.begin(),replaced.begin()+start,'\n');
    auto body=replaced.substr(start);
    renderer.removed=removed;
    renderer.parser_removed=line_starts(replaced.substr(0,start)).size()-1;
    renderer.source=text;renderer.parsed=replaced;
    renderer.source_lines=line_starts(text);renderer.parsed_lines=line_starts(replaced);
    cmark_gfm_core_extensions_ensure_registered();
    auto parser=cmark_parser_new(CMARK_OPT_STRIKETHROUGH_DOUBLE_TILDE);
    for(auto name:{"table","tasklist","strikethrough"})
        cmark_parser_attach_syntax_extension(parser,cmark_find_syntax_extension(name));
    cmark_parser_feed(parser,body.data(),body.size());
    std::unique_ptr<cmark_node,decltype(&cmark_node_free)> doc(cmark_parser_finish(parser),cmark_node_free);
    cmark_parser_free(parser);
    if(!doc) throw std::runtime_error("cannot parse Markdown");
    Render result;
    if(selection.empty()) result=renderer.blocks(doc.get(),"\n\n");
    else {
        // Prefix a newline to distinguish a match on the first line from no match.
        int offset=heading_offset("\n"+text,selection);
        if(offset) {
            const char* pos=g_utf8_offset_to_pointer(text.c_str(),offset-1);
            int line=1+std::count(text.c_str(),pos,'\n')-removed;
            if(selection[0]=='^') {
                cmark_node* chosen=nullptr;
                std::function<void(cmark_node*)> visit=[&](cmark_node* n) {
                    auto type=cmark_node_get_type(n);
                    if((type&CMARK_NODE_TYPE_MASK)==CMARK_NODE_TYPE_BLOCK&&type!=CMARK_NODE_DOCUMENT&&type!=CMARK_NODE_LIST&&cmark_node_get_start_line(n)<=line&&line<=cmark_node_get_end_line(n)) chosen=n;
                    for(auto c=cmark_node_first_child(n);c;c=cmark_node_next(c)) visit(c);
                };
                visit(doc.get());if(chosen) result=renderer.block(chosen);
            } else {
                for(auto n=cmark_node_first_child(doc.get());n;n=cmark_node_next(n)) {
                    if(cmark_node_get_type(n)!=CMARK_NODE_HEADING||cmark_node_get_start_line(n)!=line) continue;
                    int level=cmark_node_get_heading_level(n);bool first=true;
                    for(;n;n=cmark_node_next(n)) {
                        if(!first&&cmark_node_get_type(n)==CMARK_NODE_HEADING&&cmark_node_get_heading_level(n)<=level) break;
                        if(!first) result.text+="\n\n";
                        first=false;append(result,renderer.block(n));
                    }
                    break;
                }
            }
        }
    }
    std::vector<Block> positions;
    for(auto b:result.blocks) {
        b.line+=removed;
        if(positions.empty()||positions.back().line!=b.line) positions.push_back(b);
    }
    result.blocks=std::move(positions);
    auto key=[](const Span& s) {return std::tie(s.start,s.end,s.style);};
    auto& spans=result.spans;
    spans.erase(std::remove_if(spans.begin(),spans.end(),[](auto& s){return s.start>=s.end;}),spans.end());
    std::sort(spans.begin(),spans.end(),[&](auto& a,auto& b){return key(a)<key(b);});
    spans.erase(std::unique(spans.begin(),spans.end(),[&](auto& a,auto& b){return key(a)==key(b);}),spans.end());
    return result;
}
}
