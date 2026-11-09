// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Lee Harrington
#include "core.hpp"
#include <array>
#include <cstdlib>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <stdexcept>

namespace notes {
namespace {
bool leap(int y) { return y % 4 == 0 && (y % 100 != 0 || y % 400 == 0); }
int days_in_month(int y, int m) {
  static const int d[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
  return m == 2 ? d[m - 1] + leap(y) : d[m - 1];
}
bool valid(const ClockTime &t) {
  return t.year >= 1900 && t.year <= 2099 && t.month >= 1 && t.month <= 12 &&
         t.day >= 1 && t.day <= days_in_month(t.year, t.month) && t.hour >= 0 &&
         t.hour <= 23 && t.minute >= 0 && t.minute <= 59 && t.second >= 0 &&
         t.second <= 59;
}
std::string pad(int n, int width) {
  std::ostringstream out;
  out << std::setw(width) << std::setfill('0') << n;
  return out.str();
}
} // namespace
ClockTime clock_now(bool strict) {
  if (const char *p = std::getenv("LCOS_NOTES_NOW")) {
    std::string s(p);
    bool shape = s.size() == 19;
    for (size_t i = 0; shape && i < s.size(); ++i) {
      char expected = i == 4 || i == 7     ? '-'
                      : i == 10            ? 'T'
                      : i == 13 || i == 16 ? ':'
                                           : 0;
      shape = expected ? s[i] == expected : s[i] >= '0' && s[i] <= '9';
    }
    if (shape) {
      ClockTime t{std::stoi(s.substr(0, 4)),  std::stoi(s.substr(5, 2)),
                  std::stoi(s.substr(8, 2)),  std::stoi(s.substr(11, 2)),
                  std::stoi(s.substr(14, 2)), std::stoi(s.substr(17, 2))};
      if (valid(t))
        return t;
    }
    if (strict)
      throw std::runtime_error("invalid LCOS_NOTES_NOW");
  }
  std::time_t now = std::time(nullptr);
  std::tm local{};
  if (!localtime_r(&now, &local))
    throw std::runtime_error("cannot read clock");
  return {local.tm_year + 1900, local.tm_mon + 1, local.tm_mday,
          local.tm_hour,        local.tm_min,     local.tm_sec};
}
std::optional<std::string> format_time(const std::string &format,
                                       const ClockTime &t, bool *has_time) {
  if (!valid(t))
    throw std::runtime_error("invalid date");
  static const std::array<std::string, 15> tokens = {
      "YYYY", "YY",   "MMMM", "MMM", "MM", "M",  "DDDD", "DD",
      "D",    "dddd", "ddd",  "HH",  "H",  "mm", "ss"};
  static const char *months[] = {
      "January", "February", "March",     "April",   "May",      "June",
      "July",    "August",   "September", "October", "November", "December"};
  static const char *days[] = {"Sunday",   "Monday", "Tuesday", "Wednesday",
                               "Thursday", "Friday", "Saturday"};
  int doy = t.day;
  for (int m = 1; m < t.month; ++m)
    doy += days_in_month(t.year, m);
  // 1900-01-01 was Monday, and all dates here are Gregorian.
  int y = t.year - 1;
  int elapsed = 365 * (t.year - 1900) + (y / 4 - y / 100 + y / 400) -
                (1899 / 4 - 1899 / 100 + 1899 / 400);
  int weekday = (elapsed + doy) % 7;
  bool time = false;
  std::string out;
  for (size_t i = 0; i < format.size();) {
    if (format[i] == '[') {
      auto end = format.find(']', i + 1);
      if (end == std::string::npos)
        return {};
      out += format.substr(i + 1, end - i - 1);
      i = end + 1;
      continue;
    }
    std::string token;
    for (const auto &candidate : tokens)
      if (!candidate.empty() &&
          format.compare(i, candidate.size(), candidate) == 0) {
        token = candidate;
        break;
      }
    if (token.empty()) {
      unsigned char c = format[i];
      if ((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z'))
        return {};
      out += format[i++];
      continue;
    }
    i += token.size();
    if (token == "YYYY")
      out += pad(t.year, 4);
    else if (token == "YY")
      out += pad(t.year % 100, 2);
    else if (token == "MMMM")
      out += months[t.month - 1];
    else if (token == "MMM")
      out += std::string(months[t.month - 1]).substr(0, 3);
    else if (token == "MM")
      out += pad(t.month, 2);
    else if (token == "M")
      out += std::to_string(t.month);
    else if (token == "DDDD")
      out += pad(doy, 3);
    else if (token == "DD")
      out += pad(t.day, 2);
    else if (token == "D")
      out += std::to_string(t.day);
    else if (token == "dddd")
      out += days[weekday];
    else if (token == "ddd")
      out += std::string(days[weekday]).substr(0, 3);
    else {
      time = true;
      if (token == "HH")
        out += pad(t.hour, 2);
      else if (token == "H")
        out += std::to_string(t.hour);
      else if (token == "mm")
        out += pad(t.minute, 2);
      else
        out += pad(t.second, 2);
    }
  }
  if (has_time)
    *has_time = time;
  return out;
}
} // namespace notes

// U9 settings use a small strict JSON reader; non-string members are discarded.
#include <glib.h>
#include <fstream>
#include <regex>
#include <map>
#include <set>
namespace notes {
namespace {
class SettingsReader {
  const std::string &s;
  size_t p = 0;
  int depth = 0;
  void ws() {
    while (p < s.size() &&
           (s[p] == ' ' || s[p] == '\t' || s[p] == '\r' || s[p] == '\n'))
      ++p;
  }
  bool take(char c) {
    ws();
    if (p < s.size() && s[p] == c) {
      ++p;
      return true;
    }
    return false;
  }
  [[noreturn]] void bad() { throw std::runtime_error("invalid JSON"); }
  unsigned hex4() {
    if (p + 4 > s.size())
      bad();
    unsigned v = 0;
    for (int i = 0; i < 4; i++) {
      char c = s[p++];
      v *= 16;
      if (c >= '0' && c <= '9')
        v += c - '0';
      else if (c >= 'a' && c <= 'f')
        v += c - 'a' + 10;
      else if (c >= 'A' && c <= 'F')
        v += c - 'A' + 10;
      else
        bad();
    }
    return v;
  }
  std::string str() {
    if (!take('"'))
      bad();
    std::string out;
    while (p < s.size()) {
      unsigned char c = s[p++];
      if (c == '"')
        return out;
      if (c < 32)
        bad();
      if (c != '\\') {
        out += char(c);
        continue;
      }
      if (p == s.size())
        bad();
      c = s[p++];
      switch (c) {
      case '"':
      case '\\':
      case '/':
        out += char(c);
        break;
      case 'b':
        out += '\b';
        break;
      case 'f':
        out += '\f';
        break;
      case 'n':
        out += '\n';
        break;
      case 'r':
        out += '\r';
        break;
      case 't':
        out += '\t';
        break;
      case 'u': {
        unsigned u = hex4();
        if (u >= 0xd800 && u <= 0xdbff) {
          if (p + 2 > s.size() || s[p++] != '\\' || s[p++] != 'u')
            bad();
          unsigned lo = hex4();
          if (lo < 0xdc00 || lo > 0xdfff)
            bad();
          u = 0x10000 + ((u - 0xd800) << 10) + (lo - 0xdc00);
        } else if (u >= 0xdc00 && u <= 0xdfff)
          bad();
        char b[6];
        int n = g_unichar_to_utf8(u, b);
        out.append(b, n);
        break;
      }
      default:
        bad();
      }
    }
    bad();
  }
  void value() {
    ws();
    if (++depth > 128)
      bad();
    if (p == s.size())
      bad();
    char c = s[p];
    if (c == '"')
      str();
    else if (c == '{' || c == '[') {
      ++p;
      char end = c == '{' ? '}' : ']';
      if (!take(end)) {
        do {
          if (c == '{') {
            str();
            if (!take(':'))
              bad();
          }
          value();
        } while (take(','));
        if (!take(end))
          bad();
      }
    } else if (c == 't' || c == 'f' || c == 'n') {
      std::string word = c == 't' ? "true" : c == 'f' ? "false" : "null";
      if (s.compare(p, word.size(), word))
        bad();
      p += word.size();
    } else {
      size_t start = p;
      if (s[p] == '-')
        ++p;
      if (p == s.size())
        bad();
      if (s[p] == '0')
        ++p;
      else {
        if (s[p] < '1' || s[p] > '9')
          bad();
        while (p < s.size() && s[p] >= '0' && s[p] <= '9')
          ++p;
      }
      if (p < s.size() && s[p] == '.') {
        ++p;
        size_t q = p;
        while (p < s.size() && s[p] >= '0' && s[p] <= '9')
          ++p;
        if (q == p)
          bad();
      }
      if (p < s.size() && (s[p] == 'e' || s[p] == 'E')) {
        ++p;
        if (p < s.size() && (s[p] == '+' || s[p] == '-'))
          ++p;
        size_t q = p;
        while (p < s.size() && s[p] >= '0' && s[p] <= '9')
          ++p;
        if (q == p)
          bad();
      }
      if (start == p)
        bad();
    }
    --depth;
  }

public:
  explicit SettingsReader(const std::string &text) : s(text) {}
  std::map<std::string, std::string> parse() {
    std::map<std::string, std::string> out;
    if (!take('{'))
      bad();
    if (!take('}')) {
      do {
        auto key = str();
        if (!take(':'))
          bad();
        ws();
        if (p < s.size() && s[p] == '"')
          out[key] = str();
        else {
          value();
          out.erase(key);
        }
      } while (take(','));
      if (!take('}'))
        bad();
    }
    ws();
    if (p != s.size())
      bad();
    return out;
  }
};
std::map<std::string, std::string> settings(const Vault &v, const char *name) {
  try {
    auto dir = v.root / ".obsidian";
    auto path = dir / name;
    if (fs::is_symlink(fs::symlink_status(dir)) ||
        !fs::is_directory(fs::symlink_status(dir)) ||
        fs::is_symlink(fs::symlink_status(path)) ||
        !fs::is_regular_file(fs::symlink_status(path)))
      return {};
    std::ifstream f(path, std::ios::binary);
    std::string s((std::istreambuf_iterator<char>(f)), {});
    if (!g_utf8_validate(s.data(), s.size(), nullptr))
      return {};
    return SettingsReader(s).parse();
  } catch (...) {
    return {};
  }
}
std::string get(const std::map<std::string, std::string> &s,
                const std::string &k, const std::string &d) {
  auto i = s.find(k);
  return i == s.end() ? d : i->second;
}
std::string folder(std::string s) {
  auto a = s.find_first_not_of(" /");
  if (a == s.npos)
    return "";
  return s.substr(a, s.find_last_not_of(" /") - a + 1);
}
std::string fmt_setting(const std::map<std::string, std::string> &s,
                        const std::string &k, const std::string &fallback,
                        const ClockTime &now, bool date_only = false) {
  auto f = get(s, k, fallback);
  bool time = false;
  if (f.empty() || !format_time(f, now, &time) || (date_only && time))
    return fallback;
  return f;
}
} // namespace
std::string template_folder(const Vault &v) {
  auto f = folder(get(settings(v, "templates.json"), "folder", "Templates"));
  return f.empty() ? "Templates" : f;
}
std::vector<std::string> templates(const Vault &v) {
  std::vector<std::string> out;
  auto prefix = fold(template_folder(v) + "/");
  for (auto &n : v.notes())
    if (fold(n).compare(0, prefix.size(), prefix) == 0)
      out.push_back(n);
  return out;
}
std::string expand_template(const Vault &v, const std::string &text,
                            const std::string &title, const ClockTime &now) {
  auto s = settings(v, "templates.json");
  auto df = fmt_setting(s, "dateFormat", "YYYY-MM-DD", now),
       tf = fmt_setting(s, "timeFormat", "HH:mm", now);
  std::string out;
  size_t pos = 0, scan = 0, delimiter = 0;
  auto space = [](char c) { return c == ' ' || c == '\t'; };
  auto lower = [](char c) {
    return c >= 'A' && c <= 'Z' ? char(c - 'A' + 'a') : c;
  };
  while (scan + 1 < text.size()) {
    if (text[scan] != '{' || text[scan + 1] != '{') {
      ++scan;
      continue;
    }
    size_t p = scan + 2;
    while (p < text.size() && space(text[p]))
      ++p;
    std::string name;
    for (const char *candidate : {"title", "date", "time"}) {
      size_t n = std::char_traits<char>::length(candidate), i = 0;
      while (i < n && p + i < text.size() && lower(text[p + i]) == candidate[i])
        ++i;
      if (i == n) {
        name = candidate;
        p += n;
        break;
      }
    }
    if (name.empty()) {
      ++scan;
      continue;
    }
    while (p < text.size() && space(text[p]))
      ++p;
    bool formatted = p < text.size() && text[p] == ':';
    size_t format_start = 0, format_end = 0;
    if (formatted) {
      format_start = ++p;
      if (delimiter < p)
        delimiter = text.find_first_of("}\r\n", p);
      if (delimiter == std::string::npos)
        delimiter = text.size();
      format_end = delimiter;
      p = delimiter;
    }
    if (p + 1 >= text.size() || text[p] != '}' || text[p + 1] != '}') {
      ++scan;
      continue;
    }
    size_t end = p + 2;
    out.append(text, pos, scan - pos);
    if (name == "title" && !formatted)
      out += title;
    else if (name != "title") {
      auto f = formatted ? text.substr(format_start, format_end - format_start)
                         : std::string();
      if (f.empty())
        f = name == "date" ? df : tf;
      auto rendered = format_time(f, now);
      if (rendered)
        out += *rendered;
      else
        out.append(text, scan, end - scan);
    } else
      out.append(text, scan, end - scan);
    pos = end;
    scan = end;
  }
  out.append(text, pos, std::string::npos);
  return out;
}
std::string template_text(const Vault &v, const std::string &path,
                          const std::string &title, const ClockTime &now) {
  Document d;
  d.load(v, path);
  return expand_template(v, d.text, title, now);
}
} // namespace notes
namespace notes {
namespace {
std::string date_string(const ClockTime &t) {
  return *format_time("YYYY-MM-DD", t);
}
ClockTime shift(ClockTime t, int n) {
  while (n > 0) {
    if (++t.day > days_in_month(t.year, t.month)) {
      t.day = 1;
      if (++t.month > 12) {
        t.month = 1;
        ++t.year;
      }
    }
    --n;
    if (t.year > 2099)
      throw std::runtime_error("invalid date");
  }
  while (n < 0) {
    if (--t.day < 1) {
      if (--t.month < 1) {
        t.month = 12;
        --t.year;
      }
      if (t.year < 1900)
        throw std::runtime_error("invalid date");
      t.day = days_in_month(t.year, t.month);
    }
    ++n;
  }
  return t;
}
ClockTime parse_date(const ClockTime &now, const std::string &arg) {
  if (arg == "today")
    return now;
  if (arg == "yesterday")
    return shift(now, -1);
  if (arg == "tomorrow")
    return shift(now, 1);
  if (arg.size() >= 2 && arg.size() <= 6 && (arg[0] == '+' || arg[0] == '-') &&
      arg.find_first_not_of("0123456789", 1) == std::string::npos)
    return shift(now, (arg[0] == '-' ? -1 : 1) * std::stoi(arg.substr(1)));
  static const std::regex re("[0-9]{4}-[0-9]{2}-[0-9]{2}");
  if (!std::regex_match(arg, re))
    throw std::runtime_error("invalid date");
  ClockTime t{std::stoi(arg.substr(0, 4)),
              std::stoi(arg.substr(5, 2)),
              std::stoi(arg.substr(8, 2)),
              now.hour,
              now.minute,
              now.second};
  if (!valid(t))
    throw std::runtime_error("invalid date");
  return t;
}
Maybe exact_note(const Vault &v, const std::string &path) {
  auto f = fold(path);
  for (auto &n : v.notes())
    if (fold(n) == f)
      return n;
  return {};
}
std::string daily_path(const Vault &v, const ClockTime &t) {
  auto s = settings(v, "daily-notes.json");
  auto dir = folder(get(s, "folder", ""));
  auto fmt = fmt_setting(s, "format", "YYYY-MM-DD", t, true);
  return (dir.empty() ? "" : dir + "/") + *format_time(fmt, t) + ".md";
}
void write_new(const Vault &v, const std::string &path,
               const std::string &content) {
  v.create(path.substr(0, path.size() - 3), true, content);
}
} // namespace
Daily daily(const Vault &v, const ClockTime &now, const std::string &arg,
            bool create) {
  auto t = parse_date(now, arg);
  auto path = daily_path(v, t);
  auto found = exact_note(v, path);
  if (found)
    return {*found, date_string(t), true, false};
  if (create) {
    auto s = settings(v, "daily-notes.json");
    auto target = trim(get(s, "template", ""));
    std::string content;
    if (!target.empty()) {
      auto resolved = v.resolve("", target);
      if (resolved && is_note(*resolved))
        content =
            template_text(v, *resolved, fs::path(path).stem().string(), t);
    }
    write_new(v, path, content);
  }
  return {path, date_string(t), false, create};
}
std::vector<Daily> dailies(const Vault &v, const ClockTime &now) {
  auto config = settings(v, "daily-notes.json");
  auto dir = folder(get(config, "folder", ""));
  auto fmt = fmt_setting(config, "format", "YYYY-MM-DD", now, true);
  std::map<std::string, std::pair<int, std::string>> hits;
  std::set<std::string> wanted;
  for (auto &n : v.notes())
    wanted.insert(fold(n));
  for (ClockTime t{1900, 1, 1, now.hour, now.minute, now.second};
       t.year <= 2099;) {
    auto p =
        fold((dir.empty() ? "" : dir + "/") + *format_time(fmt, t) + ".md");
    if (wanted.count(p)) {
      auto &h = hits[p];
      ++h.first;
      h.second = date_string(t);
    }
    if (t.year == 2099 && t.month == 12 && t.day == 31)
      break;
    t = shift(t, 1);
  }
  std::vector<Daily> out;
  for (auto &n : v.notes()) {
    auto i = hits.find(fold(n));
    if (i != hits.end() && i->second.first == 1)
      out.push_back({n, i->second.second, true, false});
  }
  std::sort(out.begin(), out.end(), [](const Daily &a, const Daily &b) {
    return std::tie(a.date, a.path) < std::tie(b.date, b.path);
  });
  return out;
}
std::string unique_target(const Vault &v, const ClockTime &now) {
  auto s = settings(v, "zk-prefixer.json");
  auto dir = folder(get(s, "folder", ""));
  auto fmt = fmt_setting(s, "format", "YYYYMMDDHHmm", now);
  auto base = (dir.empty() ? "" : dir + "/") + *format_time(fmt, now);
  auto target = base;
  for (int i = 1; exact_note(v, target + ".md"); ++i)
    target = base + "-" + std::to_string(i);
  validated_target(target);
  return target;
}
std::pair<std::string, bool> create_template(const Vault &v,
                                             const std::string &target,
                                             const std::string &path,
                                             const ClockTime &now) {
  Document d;
  d.load(v, path);
  auto clean = validated_target(target);
  auto text =
      expand_template(v, d.text, fs::path(clean).filename().string(), now);
  return v.create(target, false, text);
}
Capture capture(const Vault &v, const ClockTime &now, const std::string &input,
                bool inbox) {
  std::string x;
  for (size_t i = 0; i < input.size(); ++i)
    if (input[i] != '\r')
      x += input[i];
  auto start = x.find_first_not_of(" \t\n");
  if (start == x.npos)
    throw std::runtime_error("nothing to capture");
  x = x.substr(start, x.find_last_not_of(" \t\n") - start + 1);
  std::string path;
  bool created = false;
  if (inbox) {
    auto found = exact_note(v, "Inbox.md");
    if (found)
      path = *found;
    else {
      write_new(v, "Inbox.md", "");
      path = "Inbox.md";
      created = true;
    }
  } else {
    auto d = daily(v, now, "today", true);
    path = d.path;
    created = d.created;
  }
  Document d;
  d.load(v, path);
  auto c = d.text;
  auto n = c.find('\n');
  std::string e = n != c.npos && n > 0 && c[n - 1] == '\r' ? "\r\n" : "\n";
  if (!c.empty() && c.back() != '\n')
    c += e;
  int line = 1 + std::count(c.begin(), c.end(), '\n');
  c += "- " + *format_time("HH:mm", now) + " ";
  size_t p = 0;
  bool first = true;
  while (true) {
    auto q = x.find('\n', p);
    auto part = x.substr(p, q == x.npos ? x.npos : q - p);
    if (!first && !part.empty())
      c += "  ";
    c += part + e;
    first = false;
    if (q == x.npos)
      break;
    p = q + 1;
  }
  d.save(v, c);
  return {path, line, created};
}
} // namespace notes
