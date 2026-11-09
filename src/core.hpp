// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Lee Harrington
#pragma once
#include <filesystem>
#include <optional>
#include <string>
#include <vector>
#include <sys/stat.h>
#include <map>
#include <stdexcept>
namespace notes {
namespace fs = std::filesystem;
using Maybe = std::optional<std::string>;
struct ClockTime { int year, month, day, hour, minute, second; };
ClockTime clock_now(bool strict = true);
std::optional<std::string> format_time(const std::string& format, const ClockTime& time, bool* has_time = nullptr);
std::string trim(std::string s);
std::string fold(const std::string& s);
std::string quote(const std::string& s);
std::string json(const Maybe& s);
bool is_note(const std::string& s);
struct Link {
    std::string raw, target;
    Maybe heading, alias, resolved;
    bool embed = false, markdown = false, angle = false;
    std::string text;
    int line = 1, col = 1, offset = 0, length = 0;
};
Link parts(std::string inner);
std::vector<Link> parse(const std::string& text);
std::vector<Link> parse_markdown(const std::string& text);
std::vector<Link> parse_all(const std::string& text);
std::string creation_target(const std::string& source, const Link& link);
struct Tag {
    std::string tag;
    int count = 0;
    // Sorted membership for listed tags, including implicit ancestors that are
    // not valid public tagged/retag arguments (for example "2025" or "").
    std::vector<std::string> notes;
};
struct Match { std::string path, text; int line, col; };
struct Backlink { std::string source, raw, text; int line, col; };
struct Rewrite { int start, end, length; };
struct Rename {
    std::string from, to;
    std::vector<std::string> updated;
    // Actual replacements in the renamed note, in original code point coordinates.
    std::vector<Rewrite> rewrites;
    std::map<std::string,std::vector<Rewrite>> note_rewrites;
    int map_caret(int offset) const;
};
struct Property { std::string key, scalar; std::vector<std::string> values; bool list=false, unsupported=false; size_t start=0, end=0; };
struct Heading { int level; std::string text; int line; };
std::vector<Property> properties(const std::string&);
std::vector<std::string> scalar_property_tags(const std::string&, const Property&);
std::vector<Heading> headings(const std::string&);
struct Span { int start, end; std::string style; };
struct RenderLink { int start, end; std::string raw; Maybe resolved; std::string source; };
struct RenderImage { int offset; std::string path; };
struct Block { int line, offset; };
struct Task {
    int line, col; bool checked; int offset;
    // Byte offset of the character after '[' in the original, unmodified source.
    size_t source_offset = 0;
};
struct Render { std::string text; std::vector<Span> spans; std::vector<Span> layout_spans; std::vector<RenderLink> links; std::vector<RenderImage> images; std::vector<Block> blocks; std::vector<Task> tasks; };
class Vault {
public:
    fs::path root;
    explicit Vault(fs::path path);
    std::vector<std::string> files() const;
    std::vector<std::string> directories() const;
    std::vector<std::string> notes() const;
    void require_note(const std::string& path) const;
    Maybe resolve(const std::string& source, std::string target, bool* via_alias=nullptr) const;
    std::vector<Link> links(const std::string& source, const std::string& text) const;
    std::vector<Link> mdlinks(const std::string& source, const std::string& text) const;
    std::vector<Link> all_links(const std::string& source, const std::string& text) const;
    std::vector<std::string> search(const std::string& query, std::map<std::string,std::string>* matched_aliases = nullptr) const;
    std::vector<Tag> tags() const;
    std::vector<std::string> tagged(std::string tag) const;
    std::vector<Match> find(const std::string& query, bool regex=false, bool word=false) const;
    std::vector<Backlink> backlinks(const std::string& note) const;
    Render render(const std::string& source, const std::string& text, const std::string& selection = "") const;
    Rename retag(std::string old, std::string target) const;
    std::vector<Backlink> mentions(const std::string& note) const;
    Rename rename(const std::string& old, std::string target) const;
    std::pair<std::string, bool> create(std::string target, bool exact=false, const std::string& contents="") const;
};
std::vector<std::pair<std::string,std::string>> aliases(const Vault&);
struct SupersedePartialSave : std::runtime_error { using std::runtime_error::runtime_error; };
void supersede(const Vault&, const std::string&, const std::string&);
class Document {
    struct stat stamp{};
    std::string original;
    bool missing=false;
public:
    std::string path, text;
    bool deleted() const {return missing;}
    void mark_deleted() {missing=true;}
    bool changed(const Vault& vault) const;
    void load(const Vault& vault, const std::string& relative);
    void save(const Vault& vault, const std::string& contents);
};
std::string validated_target(std::string target, bool note=true, bool normalize=true);
struct Daily { std::string path, date; bool exists, created; };
struct Capture { std::string path; int line; bool created; };
Daily daily(const Vault&, const ClockTime&, const std::string& date="today", bool create=false);
std::vector<Daily> dailies(const Vault&, const ClockTime&);
std::string unique_target(const Vault&, const ClockTime&);
Capture capture(const Vault&, const ClockTime&, const std::string&, bool inbox);
std::pair<std::string,bool> create_template(const Vault&,const std::string&,const std::string&,const ClockTime&);
std::string template_folder(const Vault& v);
std::vector<std::string> templates(const Vault& v);
std::string expand_template(const Vault& v, const std::string& text, const std::string& title, const ClockTime& now);
std::string template_text(const Vault& v, const std::string& path, const std::string& title, const ClockTime& now);
int heading_offset(const std::string& text, const std::string& heading);
}
