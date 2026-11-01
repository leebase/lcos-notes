// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Lee Harrington
#include "core.hpp"
#include <cmark.h>
#include <glib.h>
#include <algorithm>
#include <map>
#include <memory>
#include <set>
#include <stdexcept>
#include <tuple>

namespace notes {
namespace {
int count(const std::string& s) { return g_utf8_strlen(s.data(), s.size()); }
std::string utf8(gunichar c) { char b[6]; auto n=g_unichar_to_utf8(c,b);return std::string(b,n); }
void append(Render& out, Render part) {
    int offset=count(out.text);out.text+=part.text;
    for(auto s:part.spans) {s.start+=offset;s.end+=offset;out.spans.push_back(s);}
    for(auto l:part.links) {l.start+=offset;l.end+=offset;out.links.push_back(l);}
}
void style(Render& r,const std::string& name) {r.spans.push_back({0,count(r.text),name});}
std::string literal(cmark_node* n) {auto s=cmark_node_get_literal(n);return s?s:"";}
struct Renderer {
    std::map<gunichar,Link> tokens;
    std::string source_name;
    Render expand(const std::string& text,bool raw) const {
        Render r;
        for(const char* p=text.data();p<text.data()+text.size();p=g_utf8_next_char(p)) {
            auto c=g_utf8_get_char(p);auto found=tokens.find(c);
            if(found==tokens.end()) {r.text+=utf8(c);continue;}
            auto& l=found->second;
            if(raw) {r.text+=l.raw;continue;}
            std::string display;
            if(l.alias&&!l.alias->empty()) display=*l.alias;
            else if(l.heading&&!l.heading->empty()) display=(l.target.empty()?"":l.target+" > ")+*l.heading;
            else display=l.target.empty()?source_name:l.target;
            int start=count(r.text);r.text+=display;int end=count(r.text);
            r.spans.push_back({start,end,l.resolved?"link":"unresolved"});
            r.links.push_back({start,end,l.raw,l.resolved});
        }
        return r;
    }
    Render inlines(cmark_node* n) const {
        Render r;for(auto c=cmark_node_first_child(n);c;c=cmark_node_next(c)) append(r,inline_node(c));return r;
    }
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
        for(auto& s:r.spans) {s.start=start(s.start);s.end=end(s.end);}
        for(auto& l:r.links) {l.start=start(l.start);l.end=end(l.end);}
        r.text=std::move(text);return r;
    }
    Render block(cmark_node* n) const {
        Render r;auto type=cmark_node_get_type(n);
        switch(type) {
        case CMARK_NODE_PARAGRAPH:return inlines(n);
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
        case CMARK_NODE_BLOCK_QUOTE:r=blocks(n,"\n\n");style(r,"quote");return r;
        case CMARK_NODE_LIST: {
            int index=cmark_node_get_list_start(n);bool first=true;
            for(auto item=cmark_node_first_child(n);item;item=cmark_node_next(item),++index) {
                auto prefix=cmark_node_get_list_type(n)==CMARK_ORDERED_LIST?
                    std::to_string(index)+(cmark_node_get_list_delim(n)==CMARK_PAREN_DELIM?") ":". "):"• ";
                auto part=indent(blocks(item,cmark_node_get_list_tight(n)?"\n":"\n\n"),prefix);
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
Render Vault::render(const std::string& source,const std::string& text) const {
    if(!g_utf8_validate(text.data(),text.size(),nullptr)) throw std::runtime_error("note is not UTF-8 text");
    Renderer renderer;renderer.source_name=fs::path(source).stem().string();
    auto found=links(source,text);std::string replaced;size_t cursor=0;
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
        replaced+=text.substr(cursor,byte-cursor);replaced+=utf8(token);
        renderer.tokens.emplace(token++,l);cursor=byte+l.raw.size();
    }
    replaced+=text.substr(cursor);
    auto start=body_start(replaced);
    int removed=std::count(replaced.begin(),replaced.begin()+start,'\n');
    auto body=replaced.substr(start);
    std::unique_ptr<cmark_node,decltype(&cmark_node_free)> doc(cmark_parse_document(body.data(),body.size(),0),cmark_node_free);
    if(!doc) throw std::runtime_error("cannot parse Markdown");
    Render result;
    for(auto node=cmark_node_first_child(doc.get());node;node=cmark_node_next(node)) {
        if(!result.blocks.empty()) result.text+="\n\n";
        result.blocks.push_back({cmark_node_get_start_line(node)+removed,count(result.text)});
        append(result,renderer.block(node));
    }
    auto key=[](const Span& s) {return std::tie(s.start,s.end,s.style);};
    auto& spans=result.spans;
    spans.erase(std::remove_if(spans.begin(),spans.end(),[](auto& s){return s.start>=s.end;}),spans.end());
    std::sort(spans.begin(),spans.end(),[&](auto& a,auto& b){return key(a)<key(b);});
    spans.erase(std::unique(spans.begin(),spans.end(),[&](auto& a,auto& b){return key(a)==key(b);}),spans.end());
    return result;
}
}
