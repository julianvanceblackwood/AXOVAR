#include <algorithm>
#include <charconv>
#include <cmath>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace axovar {

struct Event {
    std::string id, venue, upstream, health;
    std::int64_t event_ms{}, receive_ms{}, sequence{}, price_cents{};
    std::string raw;
};

std::int64_t integer(const std::string& s, const char* field) {
    std::int64_t v{};
    const auto [p, error] = std::from_chars(s.data(), s.data()+s.size(), v);
    if (error != std::errc{} || p != s.data()+s.size())
        throw std::runtime_error(std::string("invalid integer in ")+field);
    return v;
}

std::string escape(const std::string& v) {
    std::string out = "\"";
    for (unsigned char c : v) {
        if (c == '"') out += "\\\"";
        else if (c == '\\') out += "\\\\";
        else if (c == '\n') out += "\\n";
        else if (c == '\r') out += "\\r";
        else if (c == '\t') out += "\\t";
        else if (c < 0x20) { const char hex[]="0123456789abcdef"; out += "\\u00"; out += hex[c>>4]; out += hex[c&15]; }
        else out += static_cast<char>(c);
    }
    return out + "\"";
}

std::vector<std::string> fields(const std::string& line) {
    // A strictly defined unquoted CSV subset; commas inside fields are rejected by column count.
    std::vector<std::string> result;
    std::stringstream stream(line);
    std::string field;
    while (std::getline(stream, field, ',')) result.push_back(field);
    return result;
}

std::vector<Event> load(const std::string& path) {
    std::ifstream file(path);
    if (!file) throw std::runtime_error("scenario file could not be opened");
    std::string line;
    if (!std::getline(file,line) || line != "id,event_ms,receive_ms,venue,upstream,sequence,price_cents,health")
        throw std::runtime_error("invalid scenario schema");
    std::vector<Event> result;
    std::set<std::string> identifiers;
    int line_no=1;
    while (std::getline(file,line)) {
        ++line_no;
        if (line.empty()) continue;
        auto c=fields(line);
        if (c.size() != 8) throw std::runtime_error("bad columns on line "+std::to_string(line_no));
        Event e;
        e.id=c[0]; e.event_ms=integer(c[1], "event_ms"); e.receive_ms=integer(c[2], "receive_ms");
        e.venue=c[3]; e.upstream=c[4]; e.sequence=integer(c[5], "sequence");
        e.price_cents=integer(c[6], "price_cents"); e.health=c[7]; e.raw=line;
        if (e.id.empty() || e.venue.empty() || e.upstream.empty() ||
            e.event_ms < 0 || e.receive_ms < 0 || e.sequence <= 0 || e.price_cents <= 0 ||
            (e.health != "OK" && e.health != "DEGRADED" && e.health != "UNTRUSTED"))
            throw std::runtime_error("invalid event on line "+std::to_string(line_no));
        if (!identifiers.insert(e.id).second) throw std::runtime_error("duplicate event id");
        result.push_back(e);
    }
    // Stable arrival order. We never use event time to grant earlier knowledge of late arrivals.
    std::stable_sort(result.begin(),result.end(),[](const auto& a, const auto& b){return a.receive_ms < b.receive_ms;});
    return result;
}

struct Venue {
    std::string name, upstream, health, evidence;
    std::int64_t price{}, sequence{}, event_ms{}, receive_ms{};
    int gaps{};
};

std::string json(const std::vector<Event>& events, std::size_t step, const std::string& scenario) {
    std::map<std::string,Venue> venues;
    std::vector<std::string> alerts;
    std::vector<std::int64_t> accepted_prices;
    const std::size_t limit=std::min(events.size(),step);
    const std::int64_t knowledge_ms = limit ? events[limit-1].receive_ms : 0;
    for (std::size_t i=0;i<limit;++i) {
        const Event& e=events[i];
        auto it=venues.find(e.venue);
        if (it != venues.end()) {
            if (e.sequence <= it->second.sequence) {
                alerts.push_back("REPEATED_OR_REORDERED_SEQUENCE:"+e.venue+":"+e.id);
                continue;
            }
            if (e.sequence > it->second.sequence+1) {
                alerts.push_back("SEQUENCE_GAP:"+e.venue+":"+e.id);
                it->second.gaps++;
            }
            if (it->second.upstream != e.upstream) alerts.push_back("UPSTREAM_CHANGED:"+e.venue);
        }
        Venue v{e.venue,e.upstream,e.health,e.id,e.price_cents,e.sequence,e.event_ms,e.receive_ms,it!=venues.end()?it->second.gaps:0};
        venues[e.venue]=v;
        if (e.health != "OK") alerts.push_back("DEGRADED_SOURCE:"+e.venue+":"+e.id);
    }
    std::set<std::string> trusted_upstreams;
    std::int64_t low_all=INT64_MAX,high_all=0;
    std::vector<std::int64_t> trusted;
    int degraded=0, stale=0;
    for (const auto& [name,v] : venues) {
        low_all=std::min(low_all,v.price); high_all=std::max(high_all,v.price);
        const bool is_stale=(knowledge_ms-v.receive_ms > 2500);
        if (is_stale) {stale++; alerts.push_back("STALE_SOURCE:"+name);}
        if (v.health=="OK" && !is_stale && v.gaps==0) {
            if(trusted_upstreams.insert(v.upstream).second) trusted.push_back(v.price);
            else alerts.push_back("SHARED_UPSTREAM:"+v.upstream);
        } else degraded++;
    }
    // Reference price is the average of one healthy fresh observation per independent upstream.
    long double consensus=0;
    for(auto p:trusted) consensus+=static_cast<long double>(p);
    if(!trusted.empty()) consensus/=trusted.size();
    const long double disagreement = venues.size()>1 && low_all>0 ?
        10000.0L*(static_cast<long double>(high_all-low_all)/low_all):0.0L;
    if(disagreement>150) alerts.push_back("CROSS_VENUE_DIVERGENCE");
    // Synthetic portfolio: 0.5 BTC, $35,000 USD, proposed buy 0.1 BTC.
    // At the reference price: post-action BTC exposure fraction = 0.6*p/(0.5*p + 35000).
    const long double p=consensus/100.0L;
    const long double exposure=consensus>0 ? (0.6L*p)/(0.5L*p+35000.0L) : 0.0L;
    std::string decision, explanation;
    if (trusted_upstreams.size() < 2) {
        decision="INSUFFICIENT_EVIDENCE";
        explanation="At least two fresh, gap-free, independent healthy upstreams are required.";
    } else if (disagreement>150) {
        decision="DENY_SIMULATION";
        explanation="Cross-venue disagreement exceeds the 150 bps market-integrity limit.";
    } else if(exposure > 0.75L) {
        decision="DENY_SIMULATION";
        explanation="Proposed BTC exposure exceeds the 75% portfolio concentration limit.";
    } else {
        decision="ALLOW_SIMULATION";
        explanation="Independent source and configured financial policy checks passed.";
    }
    std::ostringstream j;
    j<<std::fixed<<std::setprecision(4);
    j<<"{\"scenario\":"<<escape(scenario)<<",\"step\":"<<limit<<",\"total\":"<<events.size()
     <<",\"knowledge_ms\":"<<knowledge_ms<<",\"instrument\":\"BTC/USD\",\"synthetic\":true,\"events\":[";
    for (std::size_t i=0;i<limit;++i) {
        if (i) j<<",";
        auto& e=events[i];
        j<<"{\"id\":"<<escape(e.id)<<",\"venue\":"<<escape(e.venue)<<",\"upstream\":"<<escape(e.upstream)
         <<",\"event_ms\":"<<e.event_ms<<",\"receive_ms\":"<<e.receive_ms<<",\"sequence\":"<<e.sequence
         <<",\"price\":"<<static_cast<long double>(e.price_cents)/100.0L<<",\"health\":"<<escape(e.health)<<"}";
    }
    j<<"],\"venues\":[";
    bool first=true;
    for (const auto& [name,v]:venues) {
        if(!first) j<<",";
        first=false;
        const bool is_stale=knowledge_ms-v.receive_ms>2500;
        const bool valid=v.health=="OK" && !is_stale && v.gaps==0;
        j<<"{\"name\":"<<escape(name)<<",\"upstream\":"<<escape(v.upstream)
         <<",\"health\":"<<escape(is_stale?"STALE":v.health)<<",\"price\":"<<static_cast<long double>(v.price)/100.0L
         <<",\"sequence\":"<<v.sequence<<",\"gaps\":"<<v.gaps<<",\"eligible\":"<<(valid?"true":"false")
         <<",\"evidence\":"<<escape(v.evidence)<<"}";
    }
    j<<"],\"metrics\":{\"independent_healthy_sources\":"<<trusted_upstreams.size()
     <<",\"degraded_venues\":"<<degraded<<",\"stale_venues\":"<<stale
     <<",\"reference_price\":"<<p<<",\"venue_disagreement_bps\":"<<disagreement
     <<",\"btc_position\":0.5,\"usd_cash\":35000.0,\"candidate_btc_buy\":0.1"
     <<",\"post_trade_btc_exposure_pct\":"<<(exposure*100.0L)<<"},\"alerts\":[";
    for(std::size_t i=0;i<alerts.size();++i){if(i)j<<",";j<<escape(alerts[i]);}
    j<<"],\"decision\":{\"result\":"<<escape(decision)<<",\"reason\":"<<escape(explanation)
     <<",\"policy\":\"AXV-POLICY-001\",\"required_independent_sources\":2,\"max_disagreement_bps\":150,\"max_post_trade_exposure_pct\":75"
     <<",\"evidence_ids\":[";
    first=true;
    for(auto& [name,v]:venues){if(!first)j<<",";first=false;j<<escape(v.evidence);}
    j<<"]}}";
    return j.str();
}
} // namespace axovar

int main(int argc,char** argv) {
    try {
        if(argc!=4 || std::string(argv[1])!="--scenario") {
            std::cerr<<"Usage: axovar_core --scenario FILE STEP\n"; return 2;
        }
        std::string path=argv[2];
        const auto step=axovar::integer(argv[3],"step");
        if(step<0) throw std::runtime_error("step must be nonnegative");
        const auto events=axovar::load(path);
        auto slash=path.find_last_of("/\\");
        auto name=path.substr(slash==std::string::npos?0:slash+1);
        std::cout<<axovar::json(events,static_cast<std::size_t>(step),name)<<'\n';
    } catch(const std::exception& e) {
        std::cerr<<"AXOVAR input error: "<<e.what()<<'\n'; return 1;
    }
}
