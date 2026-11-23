// MiniDesktop <-> Discord Social SDK köprüsü.
//
// Kullanım: dcbridge.exe <application_id> <token_dosyası>
// stdout: satır başına bir JSON olay   (status / self / friends / message / log)
// stdin : "reauth" -> yeniden yetkilendir, "quit" ya da EOF -> çık
#define DISCORDPP_IMPLEMENTATION
#include "discordpp.h"

#include <atomic>
#include <chrono>
#include <cstdio>
#include <fcntl.h>
#include <fstream>
#include <functional>
#include <io.h>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <vector>

using namespace std::chrono_literals;

static std::mutex g_outMu;
static std::atomic<bool> g_running{true};
static std::atomic<bool> g_reauth{false};

static std::string esc(const std::string& s) {
    std::string o;
    o.reserve(s.size() + 2);
    o += '"';
    for (unsigned char c : s) {
        switch (c) {
            case '"': o += "\\\""; break;
            case '\\': o += "\\\\"; break;
            case '\n': o += "\\n"; break;
            case '\r': o += "\\r"; break;
            case '\t': o += "\\t"; break;
            default:
                if (c < 0x20) {
                    char b[8];
                    std::snprintf(b, sizeof b, "\\u%04x", c);
                    o += b;
                } else {
                    o += static_cast<char>(c);
                }
        }
    }
    o += '"';
    return o;
}

static void emit(const std::string& json) {
    std::lock_guard<std::mutex> lock(g_outMu);
    std::fwrite(json.data(), 1, json.size(), stdout);
    std::fputc('\n', stdout);
    std::fflush(stdout);
}

static void emitStatus(const std::string& status, const std::string& error = "") {
    emit("{\"t\":\"status\",\"status\":" + esc(status) + ",\"error\":" + esc(error) + "}");
}

static void emitLog(const std::string& msg) { emit("{\"t\":\"log\",\"msg\":" + esc(msg) + "}"); }

static std::string avatarUrl(uint64_t id, const std::optional<std::string>& hash) {
    if (hash && !hash->empty())
        return "https://cdn.discordapp.com/avatars/" + std::to_string(id) + "/" + *hash + ".png?size=64";
    return "https://cdn.discordapp.com/embed/avatars/" + std::to_string((id >> 22) % 6) + ".png";
}

static const char* statusName(discordpp::StatusType s) {
    switch (s) {
        case discordpp::StatusType::Online: return "online";
        case discordpp::StatusType::Idle: return "idle";
        case discordpp::StatusType::Dnd: return "dnd";
        case discordpp::StatusType::Streaming: return "streaming";
        case discordpp::StatusType::Invisible:
        case discordpp::StatusType::Offline: return "offline";
        default: return "unknown";
    }
}

static std::string userJson(const discordpp::UserHandle& u) {
    std::ostringstream o;
    o << "{\"id\":" << esc(std::to_string(u.Id())) << ",\"name\":" << esc(u.DisplayName())
      << ",\"username\":" << esc(u.Username()) << ",\"avatar\":" << esc(avatarUrl(u.Id(), u.Avatar()))
      << ",\"status\":" << esc(statusName(u.Status())) << "}";
    return o.str();
}

// ----- token dosyası: 3 satır (access, refresh, bitiş unix zamanı) -----
struct Tokens {
    std::string access, refresh;
    long long expiresAt = 0;
};
static Tokens loadTokens(const std::string& path) {
    Tokens t;
    std::ifstream f(path);
    std::string exp;
    if (f) {
        std::getline(f, t.access);
        std::getline(f, t.refresh);
        std::getline(f, exp);
        try { t.expiresAt = std::stoll(exp); } catch (...) {}
    }
    return t;
}
static void saveTokens(const std::string& path, const Tokens& t) {
    std::ofstream f(path, std::ios::trunc);
    f << t.access << "\n" << t.refresh << "\n" << t.expiresAt << "\n";
}

int main(int argc, char** argv) {
    _setmode(_fileno(stdout), _O_BINARY);
    if (argc < 3) {
        std::fprintf(stderr, "kullanim: dcbridge <application_id> <token_dosyasi>\n");
        return 2;
    }
    const uint64_t appId = std::stoull(argv[1]);
    const std::string tokenPath = argv[2];

    std::thread([] {
        char buf[256];
        while (std::fgets(buf, sizeof buf, stdin)) {
            std::string line(buf);
            if (line.rfind("quit", 0) == 0) break;
            if (line.rfind("reauth", 0) == 0) g_reauth = true;
        }
        g_running = false;
    }).detach();

    auto client = std::make_shared<discordpp::Client>();
    uint64_t selfId = 0;
    bool friendsDirty = false;
    auto lastDirty = std::chrono::steady_clock::now();
    auto markDirty = [&] {
        friendsDirty = true;
        lastDirty = std::chrono::steady_clock::now();
    };

    client->AddLogCallback([](auto message, auto) { emitLog(std::string(message)); },
                           discordpp::LoggingSeverity::Warning);

    client->SetStatusChangedCallback([&](discordpp::Client::Status status, discordpp::Client::Error error,
                                         int32_t detail) {
        if (status == discordpp::Client::Status::Ready) {
            auto me = client->GetCurrentUserV2();
            if (me) {
                selfId = me->Id();
                emit("{\"t\":\"self\",\"user\":" + userJson(*me) + "}");
            }
            emitStatus("ready");
            markDirty();
        } else if (error != discordpp::Client::Error::None) {
            emitStatus("error", discordpp::Client::ErrorToString(error) + " (" + std::to_string(detail) + ")");
        } else if (status == discordpp::Client::Status::Disconnected) {
            emitStatus("disconnected");
        } else {
            emitStatus("connecting");
        }
    });

    client->SetRelationshipCreatedCallback([&](auto, auto) { markDirty(); });
    client->SetRelationshipDeletedCallback([&](auto, auto) { markDirty(); });
    client->SetUserUpdatedCallback([&](auto) { markDirty(); });

    client->SetMessageCreatedCallback([&](uint64_t messageId) {
        auto m = client->GetMessageHandle(messageId);
        if (!m) return;
        const uint64_t author = m->AuthorId();
        const bool mine = author == selfId;
        const uint64_t partner = mine ? m->RecipientId() : author;
        if (partner == 0) return;  // DM değil (lobi vb.)
        std::string authorJson = "null";
        if (auto a = m->Author()) authorJson = userJson(*a);
        std::ostringstream o;
        o << "{\"t\":\"message\",\"self\":" << (mine ? "true" : "false") << ",\"partner\":"
          << esc(std::to_string(partner)) << ",\"channel\":" << esc(std::to_string(m->ChannelId()))
          << ",\"author\":" << authorJson << ",\"content\":" << esc(m->Content()) << "}";
        emit(o.str());
    });

    Tokens tokens = loadTokens(tokenPath);
    std::function<void()> authorize;
    bool refreshing = false;

    auto onToken = [&](discordpp::ClientResult result, std::string accessToken, std::string refreshToken,
                       discordpp::AuthorizationTokenType tokenType, int32_t expiresIn, std::string) {
        if (!result.Successful()) {
            if (refreshing) {
                refreshing = false;
                authorize();  // yenileme başarısız: baştan yetki iste
            } else {
                emitStatus("error", "Token alınamadı: " + result.Error());
            }
            return;
        }
        refreshing = false;
        tokens.access = accessToken;
        tokens.refresh = refreshToken;
        tokens.expiresAt = std::chrono::duration_cast<std::chrono::seconds>(
                               std::chrono::system_clock::now().time_since_epoch())
                               .count() +
                           expiresIn;
        saveTokens(tokenPath, tokens);
        emitStatus("connecting");
        client->UpdateToken(tokenType, accessToken, [&](discordpp::ClientResult r) {
            if (r.Successful())
                client->Connect();
            else
                emitStatus("error", "Token kullanılamadı: " + r.Error());
        });
    };

    authorize = [&] {
        emitStatus("authorizing");
        auto verifier = client->CreateAuthorizationCodeVerifier();
        discordpp::AuthorizationArgs args{};
        args.SetClientId(appId);
        args.SetScopes(discordpp::Client::GetDefaultCommunicationScopes());
        args.SetCodeChallenge(verifier.Challenge());
        client->Authorize(args, [&, verifier](discordpp::ClientResult result, std::string code,
                                              std::string redirectUri) {
            if (!result.Successful()) {
                emitStatus("error", "Yetki verilmedi: " + result.Error());
                return;
            }
            client->GetToken(appId, code, verifier.Verifier(), redirectUri, onToken);
        });
    };

    if (!tokens.refresh.empty()) {
        refreshing = true;
        emitStatus("connecting");
        client->RefreshToken(appId, tokens.refresh, onToken);
    } else {
        authorize();
    }

    while (g_running) {
        discordpp::RunCallbacks();
        if (g_reauth.exchange(false)) {
            std::remove(tokenPath.c_str());
            tokens = Tokens{};
            client->Disconnect();
            authorize();
        }
        if (friendsDirty && std::chrono::steady_clock::now() - lastDirty > 300ms) {
            friendsDirty = false;
            std::ostringstream o;
            o << "{\"t\":\"friends\",\"friends\":[";
            bool first = true;
            for (auto& rel : client->GetRelationships()) {
                if (rel.DiscordRelationshipType() != discordpp::RelationshipType::Friend) continue;
                auto u = rel.User();
                if (!u) continue;
                if (!first) o << ",";
                first = false;
                o << userJson(*u);
            }
            o << "]}";
            emit(o.str());
        }
        std::this_thread::sleep_for(10ms);
    }
    client->Disconnect();
    for (int i = 0; i < 20; ++i) {
        discordpp::RunCallbacks();
        std::this_thread::sleep_for(10ms);
    }
    return 0;
}
