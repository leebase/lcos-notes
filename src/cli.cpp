// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Lee Harrington
#include "core.hpp"
#include <iostream>
using namespace notes;
static std::string array(const std::vector<std::string>& values) {
    std::string out="["; bool first=true;
    for(auto& s:values) {if(!first) out+=",";
                first=false;out+=quote(s);} return out+"]";
}
static std::string fields(const Link& l) {
    return "\"target\":"+quote(l.target)+",\"heading\":"+json(l.heading)+",\"alias\":"+json(l.alias)+",\"resolved\":"+json(l.resolved);
}
int main(int argc,char** argv) {
    try {
        if(argc<3) throw std::runtime_error("usage: lcos-notes-cli notes|links|mdlinks|resolve|switch|create|tags|tagged|find|backlinks|mentions|retag|rename|render|blocks VAULT [arguments]");
        std::string command=argv[1],out; Vault vault(argv[2]);
        if(command=="notes" && argc==3) out=array(vault.notes());
        else if(command=="blocks" && argc==4) {
            Document doc;doc.load(vault,argv[3]);auto r=vault.render(doc.path,doc.text);
            out="[";
            for(auto& b:r.blocks) {if(out.size()>1) out+=",";out+="{\"line\":"+std::to_string(b.line)+",\"offset\":"+std::to_string(b.offset)+"}";}
            out+="]";
        }
        else if(command=="render" && argc==4) {
            Document doc;doc.load(vault,argv[3]);auto r=vault.render(doc.path,doc.text);
            out="{\"text\":"+quote(r.text)+",\"spans\":[";
            for(auto& s:r.spans) {if(out.back()!= '[') out+=",";out+="{\"start\":"+std::to_string(s.start)+",\"end\":"+std::to_string(s.end)+",\"style\":"+quote(s.style)+"}";}
            out+="],\"links\":[";
            for(auto& l:r.links) {if(out.back()!= '[') out+=",";out+="{\"start\":"+std::to_string(l.start)+",\"end\":"+std::to_string(l.end)+",\"raw\":"+quote(l.raw)+",\"resolved\":"+json(l.resolved)+"}";}
            out+="]}";
        }
        else if(command=="tags" && argc==3) {
            out="[";for(auto& t:vault.tags()) {if(out.size()>1) out+=",";out+="{\"tag\":"+quote(t.tag)+",\"count\":"+std::to_string(t.count)+"}";}out+="]";
        } else if(command=="tagged" && argc==4) out=array(vault.tagged(argv[3]));
        else if(command=="find" && argc>=4) {
            bool regex=false,word=false;
            for(int i=4;i<argc;++i) {
                std::string option=argv[i];
                if(option=="--regex") regex=true;
                else if(option=="--word") word=true;
                else throw std::runtime_error("invalid find option");
            }
            out="[";for(auto& m:vault.find(argv[3],regex,word)) {if(out.size()>1) out+=",";out+="{\"path\":"+quote(m.path)+",\"line\":"+std::to_string(m.line)+",\"col\":"+std::to_string(m.col)+",\"text\":"+quote(m.text)+"}";}out+="]";
        } else if(command=="backlinks" && argc==4) {
            out="[";for(auto& b:vault.backlinks(argv[3])) {if(out.size()>1) out+=",";out+="{\"source\":"+quote(b.source)+",\"line\":"+std::to_string(b.line)+",\"col\":"+std::to_string(b.col)+",\"raw\":"+quote(b.raw)+"}";}out+="]";
        } else if(command=="mentions" && argc==4) {
            out="[";
            for(auto& m:vault.mentions(argv[3])) {
                if(out.size()>1) out+=",";
                out+="{\"source\":"+quote(m.source)+",\"line\":"+std::to_string(m.line)+",\"col\":"+std::to_string(m.col)+",\"text\":"+quote(m.text)+"}";
            }
            out+="]";
        } else if((command=="rename"||command=="retag") && argc==5) {
            auto r=command=="rename"?vault.rename(argv[3],argv[4]):vault.retag(argv[3],argv[4]);out="{\"from\":"+quote(r.from)+",\"to\":"+quote(r.to)+",\"updated\":"+array(r.updated)+"}";
        }
        else if(command=="switch" && argc==4) out=array(vault.search(argv[3]));
        else if(command=="create" && argc==4) {
            auto result=vault.create(argv[3]); out="{\"path\":"+quote(result.first)+",\"created\":"+(result.second?"true":"false")+"}";
        } else if(command=="resolve" && argc==5) {
            vault.require_note(argv[3]); auto l=parts(argv[4]); l.resolved=vault.resolve(argv[3],l.target); out="{"+fields(l)+"}";
        } else if(command=="mdlinks" && argc==4) {
            Document doc;doc.load(vault,argv[3]);out="[";
            for(auto& l:vault.mdlinks(doc.path,doc.text)) {
                if(out.size()>1) out+=",";
                out+="{\"raw\":"+quote(l.raw)+",\"text\":"+quote(l.text)+",\"path\":"+quote(l.target)+",\"heading\":"+json(l.heading)+",\"line\":"+std::to_string(l.line)+",\"col\":"+std::to_string(l.col)+",\"resolved\":"+json(l.resolved)+"}";
            }
            out+="]";
        } else if(command=="links" && argc==4) {
            Document doc;doc.load(vault,argv[3]);out="[";bool first=true;
            for(auto& l:vault.links(doc.path,doc.text)) {
                if(!first) out+=",";
                first=false;
                out+="{\"raw\":"+quote(l.raw)+","+fields(l)+",\"embed\":"+(l.embed?"true":"false")+",\"line\":"+std::to_string(l.line)+",\"col\":"+std::to_string(l.col)+"}";
            }
            out+="]";
        } else throw std::runtime_error("invalid command or arguments");
        std::cout<<out<<'\n';return 0;
    } catch(const std::exception& e) {
        std::string message=e.what();
        for(char& c:message) if(c=='\n' || c=='\r') c=' ';
        std::cerr<<"refused: "<<message<<'\n';return 2;
    }
}
