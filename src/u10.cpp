// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Lee Harrington
#include "core.hpp"
#include <algorithm>
#include <cmark-gfm.h>
#include <cmark-gfm-core-extensions.h>
#include <glib.h>
#include <memory>
#include <stdexcept>
namespace notes {
namespace {
struct Line { size_t start, end, next; std::string text; };
std::vector<Line> lines(const std::string& s) {
    std::vector<Line> out;
    for(size_t a=0;a<s.size();) {auto b=s.find('\n',a); if(b==s.npos)b=s.size(); auto t=s.substr(a,b-a); if(!t.empty()&&t.back()=='\r')t.pop_back(); out.push_back({a,b,b<s.size()?b+1:b,t});a=b<s.size()?b+1:b;}
    return out;
}
bool keyline(const std::string& s,size_t& colon) {
    colon=s.find(':');if(colon==s.npos||colon==0||!(g_ascii_isalpha(s[0])||s[0]=='_'))return false;
    for(size_t i=1;i<colon;++i)if(!(g_ascii_isalnum(s[i])||s[i]=='_'||s[i]=='-'))return false;return true;
}
std::string unquote(std::string s) {s=trim(s);if(s.size()>=2&&((s.front()=='"'&&s.back()=='"')||(s.front()=='\''&&s.back()=='\'')))s=s.substr(1,s.size()-2);return s;}
bool item(const std::string& s) {auto p=s.find_first_not_of(" \t");return p!=s.npos&&p>0&&s.compare(p,2,"- ")==0;}
struct Parsed {std::vector<Property> props; std::vector<Line> ls; size_t close=0; bool opening=false,closed=false;};
Parsed parse_props(const std::string& text) {
    Parsed p;p.ls=lines(text);if(p.ls.empty()||p.ls[0].text!="---")return p;p.opening=true;
    for(size_t i=1;i<p.ls.size();++i)if(p.ls[i].text=="---"||p.ls[i].text=="..."){p.closed=true;p.close=i;break;}
    if(!p.closed)return p;
    for(size_t i=1;i<p.close;) {size_t c;if(!keyline(p.ls[i].text,c)){++i;continue;}size_t begin=i,j=i+1;while(j<p.close&&!p.ls[j].text.empty()&&(p.ls[j].text[0]==' '||p.ls[j].text[0]=='\t'))++j;
        Property prop;prop.key=p.ls[i].text.substr(0,c);prop.start=p.ls[i].start;prop.end=p.ls[j-1].next;auto raw=p.ls[i].text.substr(c+1);auto val=trim(raw);
        bool block=val.empty()&&j>i+1;bool supported=true;for(size_t k=i+1;k<j;++k)if(!item(p.ls[k].text))supported=false;
        if(!val.empty()&&j>i+1)supported=false;if(val.size()>=2&&val.front()=='{'&&val.back()=='}')supported=false;
        if(!supported){prop.unsupported=true;prop.scalar=raw;for(size_t k=i+1;k<j;++k)prop.scalar+="\n"+p.ls[k].text;}
        else if(block){prop.list=true;for(size_t k=i+1;k<j;++k){auto x=p.ls[k].text.find_first_not_of(" \t");prop.values.push_back(unquote(p.ls[k].text.substr(x+2)));}}
        else if(val.size()>=2&&val.front()=='['&&val.back()==']'){prop.list=true;auto v=val.substr(1,val.size()-2);if(!v.empty()){size_t a=0;for(;;){auto b=v.find(',',a);prop.values.push_back(unquote(v.substr(a,b==v.npos?b:b-a)));if(b==v.npos)break;a=b+1;}}}
        else prop.scalar=unquote(val);
        p.props.erase(std::remove_if(p.props.begin(),p.props.end(),[&](const Property& x){return x.key==prop.key;}),p.props.end());p.props.push_back(prop);i=std::max(j,begin+1);
    }return p;
}
void inline_text(cmark_node* n,std::string& out) {for(auto c=cmark_node_first_child(n);c;c=cmark_node_next(c)){auto t=cmark_node_get_type(c);if(t==CMARK_NODE_TEXT||t==CMARK_NODE_CODE||t==CMARK_NODE_HTML_INLINE){auto s=cmark_node_get_literal(c);if(s)out+=s;}else if(t==CMARK_NODE_SOFTBREAK||t==CMARK_NODE_LINEBREAK)out+=' ';else inline_text(c,out);}}
void find_headings(cmark_node* n,int removed,std::vector<Heading>& out){for(auto c=cmark_node_first_child(n);c;c=cmark_node_next(c)){if(cmark_node_get_type(c)==CMARK_NODE_HEADING){Heading h{cmark_node_get_heading_level(c),"",cmark_node_get_start_line(c)+removed};inline_text(c,h.text);out.push_back(h);}find_headings(c,removed,out);}}
std::string superseded_text(const std::string& text,const std::string& key,const std::string& target) {
    auto p=parse_props(text);if(p.opening&&!p.closed)throw std::runtime_error("unclosed frontmatter");
    auto newline=text.find('\n');std::string nl=newline!=text.npos&&newline>0&&text[newline-1]=='\r'?"\r\n":"\n";
    std::string field=key+": \"[["+target.substr(0,target.size()-3)+"]]\"";
    if(!p.closed)return "---"+nl+field+nl+"---"+nl+text;
    int count=0;size_t start=0,end=0;for(size_t i=1;i<p.close;++i){size_t c;if(keyline(p.ls[i].text,c)&&p.ls[i].text.substr(0,c)==key){++count;start=p.ls[i].start;size_t j=i+1;while(j<p.close&&!p.ls[j].text.empty()&&(p.ls[j].text[0]==' '||p.ls[j].text[0]=='\t'))++j;end=p.ls[j-1].next;}}
    if(count>1)throw std::runtime_error("repeated affected key");
    for(auto& prop:p.props)if(prop.key==key&&prop.unsupported)throw std::runtime_error("unsupported affected key");
    if(!count)start=end=p.ls[p.close].start;
    return text.substr(0,start)+field+nl+text.substr(end);
}
}
std::vector<Property> properties(const std::string& text){return parse_props(text).props;}
std::vector<Heading> headings(const std::string& text) {
    if(!g_utf8_validate(text.data(),text.size(),nullptr))
        throw std::runtime_error("note is not UTF-8 text");
    auto p=parse_props(text);
    size_t start=p.closed?p.ls[p.close].next:0;
    int removed=std::count(text.begin(),text.begin()+start,'\n');
    auto body=text.substr(start);
    // Match the renderer's GFM parser while keeping its output untouched.
    cmark_gfm_core_extensions_ensure_registered();
    auto parser=cmark_parser_new(CMARK_OPT_STRIKETHROUGH_DOUBLE_TILDE);
    for(auto name:{"table","tasklist","strikethrough"})
        cmark_parser_attach_syntax_extension(parser,cmark_find_syntax_extension(name));
    cmark_parser_feed(parser,body.data(),body.size());
    auto doc=std::unique_ptr<cmark_node,decltype(&cmark_node_free)>(cmark_parser_finish(parser),cmark_node_free);
    cmark_parser_free(parser);
    std::vector<Heading> out;
    if(doc) find_headings(doc.get(),removed,out);
    return out;
}
void supersede(const Vault& v,const std::string& old,const std::string& next){if(old==next)throw std::runtime_error("notes must be distinct");Document a,b;a.load(v,old);b.load(v,next);auto x=superseded_text(a.text,"superseded_by",next);auto y=superseded_text(b.text,"supersedes",old);a.save(v,x);try {b.save(v,y);} catch(const std::exception& e) {throw SupersedePartialSave(std::string("old note saved; new note failed: ")+e.what());}}
}
