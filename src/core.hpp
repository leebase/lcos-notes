// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Lee Harrington
#pragma once
#include <filesystem>
#include <optional>
#include <string>
#include <vector>
#include <sys/stat.h>
#include <map>
namespace notes {
namespace fs = std::filesystem;
using Maybe = std::optional<std::string>;
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
struct Span { int start, end; std::string style; };
struct RenderLink { int start, end; std::string raw; Maybe resolved; };
struct Block { int line, offset; };
struct Render { std::string text; std::vector<Span> spans; std::vector<RenderLink> links; std::vector<Block> blocks; };
class Vault {
public:
    fs::path root;
    explicit Vault(fs::path path);
    std::vector<std::string> files() const;
    std::vector<std::string> directories() const;
    std::vector<std::string> notes() const;
    void require_note(const std::string& path) const;
    Maybe resolve(const std::string& source, std::string target) const;
    std::vector<Link> links(const std::string& source, const std::string& text) const;
    std::vector<Link> mdlinks(const std::string& source, const std::string& text) const;
    std::vector<Link> all_links(const std::string& source, const std::string& text) const;
    std::vector<std::string> search(const std::string& query) const;
    std::vector<Tag> tags() const;
    std::vector<std::string> tagged(std::string tag) const;
    std::vector<Match> find(const std::string& query, bool regex=false, bool word=false) const;
    std::vector<Backlink> backlinks(const std::string& note) const;
    Render render(const std::string& source, const std::string& text) const;
    Rename retag(std::string old, std::string target) const;
    std::vector<Backlink> mentions(const std::string& note) const;
    Rename rename(const std::string& old, std::string target) const;
    std::pair<std::string, bool> create(std::string target) const;
};
class Document {
    struct stat stamp{};
    std::string original;
public:
    std::string path, text;
    void load(const Vault& vault, const std::string& relative);
    void save(const Vault& vault, const std::string& contents);
};
int heading_offset(const std::string& text, const std::string& heading);
}
