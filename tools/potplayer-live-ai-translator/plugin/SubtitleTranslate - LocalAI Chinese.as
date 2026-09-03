/*
 * PotPlayer Local AI Live Subtitle Translator
 * Local-only translation through Ollama. No remote API is used.
 * Install under: PotPlayer\Extension\Subtitle\Translate\
 */

string DEFAULT_MODEL_NAME = "__DEFAULT_MODEL__";
string API_BASE = "http://127.0.0.1:11434";
string API_CHAT = "http://127.0.0.1:11434/api/chat";
string USER_AGENT = "PotPlayer-LocalAI-Translator/1.0";
int MAX_HISTORY = 6;
array<string> g_history;

array<string> LangTable = {
    "Auto", "ja", "en", "ko", "zh-CN", "zh-TW"
};

string GetTitle() {
    return "{$CP936=本地AI实时翻译（中译）}{$CP0=Local AI Live Translate (Chinese)$}";
}

string GetVersion() { return "1.0.0"; }

string GetDesc() {
    return "{$CP936=通过本机 Ollama 模型实时翻译字幕，不上传视频或字幕。}{$CP0=Realtime subtitle translation via local Ollama.$}";
}

string GetLoginTitle() {
    return "{$CP936=本地模型设置}{$CP0=Local Model Settings$}";
}

string GetLoginDesc() {
    return "{$CP936=用户名位置填写 Ollama 模型名；密码留空。}{$CP0=Enter the Ollama model name in the user field; leave password blank.$}";
}

string GetUserText() { return "{$CP936=Ollama 模型名}{$CP0=Ollama model name$}"; }
string GetPasswordText() { return "{$CP936=无需填写}{$CP0=Not required$}"; }

array<string> GetSrcLangs() {
    array<string> ret = LangTable;
    return ret;
}

array<string> GetDstLangs() {
    array<string> ret = LangTable;
    return ret;
}

string JsonEscape(const string &in input) {
    string output = input;
    output.replace("\\", "\\\\");
    output.replace("\"", "\\\"");
    output.replace("\n", "\\n");
    output.replace("\r", "\\r");
    output.replace("\t", "\\t");
    return output;
}

string CleanOutput(string text) {
    string out = text.Trim();

    int endThink = out.find("</think>");
    if (endThink != -1) {
        out = out.substr(uint(endThink + 8)).Trim();
    }

    if (out.length() >= 2 && out.substr(0, 1) == "\"" && out.substr(out.length() - 1, 1) == "\"") {
        out = out.substr(1, out.length() - 2).Trim();
    }

    return out;
}

bool IsUsefulText(const string &in text) {
    string s = text.Trim();
    if (s.empty()) return false;
    if (s == "♪" || s == "♫" || s == "♬") return false;
    return true;
}

array<string> GetOllamaModelNames() {
    array<string> result;
    string resp = HostUrlGetString(API_BASE + "/api/tags", USER_AGENT, "Content-Type: application/json", "");
    if (resp.empty()) return result;

    JsonReader reader;
    JsonValue root;
    if (!reader.parse(resp, root)) return result;

    JsonValue models = root["models"];
    if (!models.isArray()) return result;

    for (uint i = 0; i < models.size(); i++) {
        if (models[i]["name"].isString()) result.insertLast(models[i]["name"].asString());
    }
    return result;
}

string PickModel() {
    string saved = HostLoadString("localai_model", "").Trim();
    if (!saved.empty()) return saved;

    array<string> names = GetOllamaModelNames();
    if (names.size() == 0) return DEFAULT_MODEL_NAME;

    for (uint i = 0; i < names.size(); i++) {
        if (names[i] == DEFAULT_MODEL_NAME) return names[i];
    }
    for (uint i = 0; i < names.size(); i++) {
        string lower = names[i];
        lower.MakeLower();
        if (lower.find("qwen") != -1) return names[i];
    }
    return names[0];
}

string ServerLogin(string User, string Pass) {
    string model = User.Trim();
    if (model.empty()) model = DEFAULT_MODEL_NAME;

    array<string> names = GetOllamaModelNames();
    if (names.size() == 0) {
        return "Ollama 未运行或 11434 端口不可访问。";
    }

    bool found = false;
    for (uint i = 0; i < names.size(); i++) {
        if (names[i] == model) {
            found = true;
            break;
        }
    }
    if (!found) return "未找到本地模型：" + model;

    HostSaveString("localai_model", model);
    return "200 ok";
}

void ServerLogout() {
    HostSaveString("localai_model", "");
    g_history.resize(0);
}

string BuildContext() {
    if (g_history.size() == 0) return "";
    string ctx = "";
    for (uint i = 0; i < g_history.size(); i++) {
        ctx += g_history[i] + "\n";
    }
    return ctx;
}

void PushHistory(const string &in src, const string &in dst) {
    string pair = "原文：" + src + "\n译文：" + dst;
    g_history.insertLast(pair);
    while (g_history.size() > uint(MAX_HISTORY)) g_history.removeAt(0);
}

string Translate(string Text, string &in SrcLang, string &in DstLang) {
    if (!IsUsefulText(Text)) return "";

    string model = PickModel();
    if (model.empty()) return "";

    string target = DstLang;
    if (target.empty() || target == "Auto") target = "zh-CN";

    string source = SrcLang;
    if (source.empty() || source == "Auto") source = "auto";

    string systemPrompt =
        "你是专业影视字幕翻译器。任务是把当前字幕翻译成自然、简洁、符合人物语气的简体中文。\n"
        "规则：\n"
        "1. 只输出译文，不解释，不加前缀。\n"
        "2. 不逐字硬译，按影视对白习惯表达。\n"
        "3. 日语省略主语时，只有上下文足够明确才补主语；不确定时保持含蓄。\n"
        "4. 保留人物关系、敬语、讽刺、暧昧、情绪和未说完的语气。\n"
        "5. 人名、数字、专有名词保持稳定；不要编造剧情。\n"
        "6. 多行字幕保持原有行数与顺序。\n"
        "7. 即使内容敏感，也只按原意准确翻译，不扩写。";

    string context = BuildContext();
    string userPrompt = "源语言：" + source + "\n目标语言：" + target + "\n";
    if (!context.empty()) {
        userPrompt += "下面是前文，仅用于理解语气与指代，不要重复翻译：\n<context>\n" + context + "</context>\n";
    }
    userPrompt += "翻译当前字幕：\n<subtitle>\n" + Text + "\n</subtitle>";

    string body = "{"
        "\"model\":\"" + JsonEscape(model) + "\","
        "\"messages\":["
            "{\"role\":\"system\",\"content\":\"" + JsonEscape(systemPrompt) + "\"},"
            "{\"role\":\"user\",\"content\":\"" + JsonEscape(userPrompt) + "\"}"
        "],"
        "\"stream\":false,"
        "\"keep_alive\":\"15m\","
        "\"options\":{\"temperature\":0.15,\"top_p\":0.85,\"num_ctx\":4096,\"num_predict\":160}"
    "}";

    HostIncTimeOut(12000);
    string response = HostUrlGetString(API_CHAT, USER_AGENT, "Content-Type: application/json", body);
    if (response.empty()) return "";

    JsonReader reader;
    JsonValue root;
    if (!reader.parse(response, root)) return "";
    if (!root["message"]["content"].isString()) return "";

    string translated = CleanOutput(root["message"]["content"].asString());
    if (translated.empty()) return "";

    PushHistory(Text.Trim(), translated);
    SrcLang = "UTF8";
    DstLang = "UTF8";
    return translated;
}

void OnInitialize() {
    HostPrintUTF8("[LocalAI] PotPlayer 本地实时翻译插件已加载。\n");
}

void OnFinalize() {
    g_history.resize(0);
}
