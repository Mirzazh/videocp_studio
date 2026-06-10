import SwiftUI
import AppKit
import Combine
import Foundation
import UniformTypeIdentifiers

private let appVersion = "1.1.2"
private let appReleaseAPIURL = URL(string: "https://api.github.com/repos/Mirzazh/videocp_studio/releases/latest")!
private let appReleasePageURL = URL(string: "https://github.com/Mirzazh/videocp_studio/releases/latest")!

struct GitHubReleaseResponse: Codable {
    var tag_name: String
    var html_url: String
    var name: String?
}

struct SchedulerConfig: Codable {
    var tasks_file: String = "mac-tasks.yaml"
    var run_interval_minutes: Int = 60
    var active_start: String = "09:00"
    var active_end: String = "23:00"
    var sync: SyncSettings = SyncSettings()
    var cleanup: CleanupSettings = CleanupSettings()
    var download: DownloadSettings = DownloadSettings()
    var publish: PublishSettings = PublishSettings()
    var automation: AutomationSettings = AutomationSettings()
    var tencent_accounts: [TencentAccount] = []
    var sources: [VideoSource] = []

    enum CodingKeys: String, CodingKey {
        case tasks_file, run_interval_minutes, active_start, active_end, sync, cleanup, download, publish, automation, tencent_accounts, sources
    }

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        tasks_file = try c.decodeIfPresent(String.self, forKey: .tasks_file) ?? tasks_file
        run_interval_minutes = try c.decodeIfPresent(Int.self, forKey: .run_interval_minutes) ?? run_interval_minutes
        active_start = try c.decodeIfPresent(String.self, forKey: .active_start) ?? active_start
        active_end = try c.decodeIfPresent(String.self, forKey: .active_end) ?? active_end
        sync = try c.decodeIfPresent(SyncSettings.self, forKey: .sync) ?? sync
        cleanup = try c.decodeIfPresent(CleanupSettings.self, forKey: .cleanup) ?? cleanup
        download = try c.decodeIfPresent(DownloadSettings.self, forKey: .download) ?? download
        publish = try c.decodeIfPresent(PublishSettings.self, forKey: .publish) ?? publish
        automation = try c.decodeIfPresent(AutomationSettings.self, forKey: .automation) ?? automation
        tencent_accounts = try c.decodeIfPresent([TencentAccount].self, forKey: .tencent_accounts) ?? tencent_accounts
        sources = try c.decodeIfPresent([VideoSource].self, forKey: .sources) ?? sources
    }
}

struct TencentAccount: Codable, Identifiable, Equatable {
    var id: String = UUID().uuidString
    var name: String = ""
    var token: String = ""
    var nickname: String = ""
    var is_guild_author: Bool = false
    var verified: Bool = false

    var displayName: String {
        let remark = name.trimmingCharacters(in: .whitespacesAndNewlines)
        if !remark.isEmpty { return remark }
        let verifiedName = nickname.trimmingCharacters(in: .whitespacesAndNewlines)
        return verifiedName.isEmpty ? "频道账号" : verifiedName
    }
}

struct SyncSettings: Codable {
    var history_file: String = "./sync_history_mac.json"
    var skill_dir: String = "~/.openclaw/workspace/skills/tencent-channel-community"
    var videos_per_task: Int = 1
    var publish_method: String = "skill"
    var skip_rate: Double = 0
    var max_video_duration_secs: Int = 0
}

struct CleanupSettings: Codable {
    var enabled: Bool = false
    var max_age_days: Int = 7
    var max_total_gb: Double = 20
}

struct DownloadSettings: Codable {
    var single_video_url: String = ""
    var profile_url_draft: String = ""
    var profiles: [DownloadProfile] = []
    var inputs_text: String = ""
    var output_dir: String = ""
    var history_file: String = "./download_history_mac.json"
    var order: String = "latest"
    var count: Int = 3
    var bilibili_download_mode: String = "tv"
    var quality: String = "best"
    var youtube_auto_token: Bool = false
    var youtube_cookies_text: String = ""
    var youtube_cookies_path: String = ""
    var ytdlp_extractor_args: String = "youtube:player_client=mweb;fetch_pot=always"
    var ytdlp_remote_components: Bool = true

    enum CodingKeys: String, CodingKey {
        case single_video_url, profile_url_draft, profiles, inputs_text, output_dir, history_file, order, count, bilibili_download_mode, quality, youtube_auto_token, youtube_cookies_text, youtube_cookies_path, ytdlp_extractor_args, ytdlp_remote_components
    }

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        single_video_url = try c.decodeIfPresent(String.self, forKey: .single_video_url) ?? single_video_url
        profile_url_draft = try c.decodeIfPresent(String.self, forKey: .profile_url_draft) ?? profile_url_draft
        profiles = try c.decodeIfPresent([DownloadProfile].self, forKey: .profiles) ?? profiles
        inputs_text = try c.decodeIfPresent(String.self, forKey: .inputs_text) ?? inputs_text
        output_dir = try c.decodeIfPresent(String.self, forKey: .output_dir) ?? output_dir
        history_file = try c.decodeIfPresent(String.self, forKey: .history_file) ?? history_file
        order = try c.decodeIfPresent(String.self, forKey: .order) ?? order
        count = try c.decodeIfPresent(Int.self, forKey: .count) ?? count
        bilibili_download_mode = try c.decodeIfPresent(String.self, forKey: .bilibili_download_mode) ?? bilibili_download_mode
        quality = try c.decodeIfPresent(String.self, forKey: .quality) ?? quality
        youtube_auto_token = try c.decodeIfPresent(Bool.self, forKey: .youtube_auto_token) ?? youtube_auto_token
        youtube_cookies_text = try c.decodeIfPresent(String.self, forKey: .youtube_cookies_text) ?? youtube_cookies_text
        youtube_cookies_path = try c.decodeIfPresent(String.self, forKey: .youtube_cookies_path) ?? youtube_cookies_path
        ytdlp_extractor_args = try c.decodeIfPresent(String.self, forKey: .ytdlp_extractor_args) ?? ytdlp_extractor_args
        ytdlp_remote_components = try c.decodeIfPresent(Bool.self, forKey: .ytdlp_remote_components) ?? ytdlp_remote_components
    }
}

struct DownloadProfile: Codable, Identifiable, Equatable {
    var id: String = UUID().uuidString
    var name: String = ""
    var url: String = ""
    var first_video_url: String = ""
    var order: String = "latest"
    var quality: String = "best"
    var count: Int = 3
    var parsed_at: String = ""

    enum CodingKeys: String, CodingKey {
        case id, name, url, first_video_url, order, quality, count, parsed_at
    }

    init() {}

    init(id: String = UUID().uuidString, name: String, url: String, first_video_url: String, order: String, quality: String = "best", count: Int, parsed_at: String) {
        self.id = id
        self.name = name
        self.url = url
        self.first_video_url = first_video_url
        self.order = order
        self.quality = quality
        self.count = count
        self.parsed_at = parsed_at
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? UUID().uuidString
        name = try c.decodeIfPresent(String.self, forKey: .name) ?? name
        url = try c.decodeIfPresent(String.self, forKey: .url) ?? url
        first_video_url = try c.decodeIfPresent(String.self, forKey: .first_video_url) ?? first_video_url
        order = try c.decodeIfPresent(String.self, forKey: .order) ?? order
        quality = try c.decodeIfPresent(String.self, forKey: .quality) ?? quality
        count = try c.decodeIfPresent(Int.self, forKey: .count) ?? count
        parsed_at = try c.decodeIfPresent(String.self, forKey: .parsed_at) ?? parsed_at
    }
}

struct DownloadHistoryEntry: Codable, Identifiable {
    var task_name: String = ""
    var content_id: String = ""
    var site: String = ""
    var author: String = ""
    var desc: String = ""
    var output_path: String = ""
    var synced_at: String = ""
    var status: String = ""
    var error: String = ""

    var id: String {
        "\(site)|\(content_id)|\(synced_at)"
    }

    var displayTime: String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let date = formatter.date(from: synced_at) ?? {
            formatter.formatOptions = [.withInternetDateTime]
            return formatter.date(from: synced_at)
        }()
        guard let date else { return synced_at }
        let output = DateFormatter()
        output.locale = Locale(identifier: "zh_CN")
        output.timeZone = .current
        output.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return output.string(from: date)
    }
}

struct DownloadHistoryFile: Codable {
    var entries: [DownloadHistoryEntry] = []
}

struct PublishSettings: Codable {
    var input_dir: String = "./downloads"
    var input_video: String = ""
    var account_id: String = ""
    var history_file: String = "./publish_history_mac.json"
    var skill_dir: String = "~/.openclaw/workspace/skills/tencent-channel-community"
    var scope: String = "author_global"
    var guild_id: String = ""
    var channel_id: String = ""
    var feed_type: Int = 1
    var limit: Int = 1
    var title_template: String = "{title}"
    var content_template: String = "{title}"
    var strip_tags_mentions: Bool = true
    var title_exclusions: String = ""
    var translate_title_zh_cn: Bool = false
    var delete_after_publish: Bool = true
    var retry_video_path: String = ""

    enum CodingKeys: String, CodingKey {
        case input_dir, input_video, account_id, history_file, skill_dir, scope, guild_id, channel_id, feed_type, limit
        case title_template, content_template, strip_tags_mentions, title_exclusions, translate_title_zh_cn
        case delete_after_publish, retry_video_path
    }

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        input_dir = try c.decodeIfPresent(String.self, forKey: .input_dir) ?? input_dir
        input_video = try c.decodeIfPresent(String.self, forKey: .input_video) ?? input_video
        account_id = try c.decodeIfPresent(String.self, forKey: .account_id) ?? account_id
        history_file = try c.decodeIfPresent(String.self, forKey: .history_file) ?? history_file
        skill_dir = try c.decodeIfPresent(String.self, forKey: .skill_dir) ?? skill_dir
        scope = try c.decodeIfPresent(String.self, forKey: .scope) ?? scope
        guild_id = try c.decodeIfPresent(String.self, forKey: .guild_id) ?? guild_id
        channel_id = try c.decodeIfPresent(String.self, forKey: .channel_id) ?? channel_id
        feed_type = try c.decodeIfPresent(Int.self, forKey: .feed_type) ?? feed_type
        limit = try c.decodeIfPresent(Int.self, forKey: .limit) ?? limit
        title_template = try c.decodeIfPresent(String.self, forKey: .title_template) ?? title_template
        content_template = try c.decodeIfPresent(String.self, forKey: .content_template) ?? content_template
        strip_tags_mentions = try c.decodeIfPresent(Bool.self, forKey: .strip_tags_mentions) ?? strip_tags_mentions
        title_exclusions = try c.decodeIfPresent(String.self, forKey: .title_exclusions) ?? title_exclusions
        translate_title_zh_cn = try c.decodeIfPresent(Bool.self, forKey: .translate_title_zh_cn) ?? translate_title_zh_cn
        delete_after_publish = try c.decodeIfPresent(Bool.self, forKey: .delete_after_publish) ?? delete_after_publish
        retry_video_path = try c.decodeIfPresent(String.self, forKey: .retry_video_path) ?? retry_video_path
    }
}

struct AutomationSettings: Codable {
    var download_enabled: Bool = false
    var download_profile_id: String = ""
    var download_interval_minutes: Int = 60
    var publish_enabled: Bool = false
    var publish_directories: [String] = []
    var publish_interval_minutes: Int = 60
    var publish_order: String = "sequential"
    var download_tasks: [ScheduledDownloadTask] = []
    var publish_tasks: [ScheduledPublishTask] = []

    enum CodingKeys: String, CodingKey {
        case download_enabled, download_profile_id, download_interval_minutes
        case publish_enabled, publish_directories, publish_interval_minutes, publish_order
        case download_tasks, publish_tasks
    }

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        download_enabled = try c.decodeIfPresent(Bool.self, forKey: .download_enabled) ?? download_enabled
        download_profile_id = try c.decodeIfPresent(String.self, forKey: .download_profile_id) ?? download_profile_id
        download_interval_minutes = try c.decodeIfPresent(Int.self, forKey: .download_interval_minutes) ?? download_interval_minutes
        publish_enabled = try c.decodeIfPresent(Bool.self, forKey: .publish_enabled) ?? publish_enabled
        publish_directories = try c.decodeIfPresent([String].self, forKey: .publish_directories) ?? publish_directories
        publish_interval_minutes = try c.decodeIfPresent(Int.self, forKey: .publish_interval_minutes) ?? publish_interval_minutes
        publish_order = try c.decodeIfPresent(String.self, forKey: .publish_order) ?? publish_order
        download_tasks = try c.decodeIfPresent([ScheduledDownloadTask].self, forKey: .download_tasks) ?? download_tasks
        publish_tasks = try c.decodeIfPresent([ScheduledPublishTask].self, forKey: .publish_tasks) ?? publish_tasks
    }
}

struct ScheduledDownloadTask: Codable, Identifiable, Equatable {
    var id: String = UUID().uuidString
    var profile_id: String = ""
    var interval_minutes: Int = 60
    var enabled: Bool = true
    var active_start: String = ""
    var active_end: String = ""

    enum CodingKeys: String, CodingKey {
        case id, profile_id, interval_minutes, enabled, active_start, active_end
    }

    init(
        id: String = UUID().uuidString,
        profile_id: String,
        interval_minutes: Int,
        enabled: Bool = true,
        active_start: String = "",
        active_end: String = ""
    ) {
        self.id = id
        self.profile_id = profile_id
        self.interval_minutes = interval_minutes
        self.enabled = enabled
        self.active_start = active_start
        self.active_end = active_end
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? UUID().uuidString
        profile_id = try c.decodeIfPresent(String.self, forKey: .profile_id) ?? ""
        interval_minutes = try c.decodeIfPresent(Int.self, forKey: .interval_minutes) ?? 60
        enabled = try c.decodeIfPresent(Bool.self, forKey: .enabled) ?? true
        active_start = try c.decodeIfPresent(String.self, forKey: .active_start) ?? ""
        active_end = try c.decodeIfPresent(String.self, forKey: .active_end) ?? ""
    }
}

struct ScheduledPublishTask: Codable, Identifiable, Equatable {
    var id: String = UUID().uuidString
    var settings_version: Int = 1
    var directories: [String] = []
    var account_id: String = ""
    var interval_minutes: Int = 60
    var order: String = "sequential"
    var enabled: Bool = true
    var active_start: String = ""
    var active_end: String = ""
    var scope: String = "author_global"
    var guild_id: String = ""
    var channel_id: String = ""
    var feed_type: Int = 1
    var limit: Int = 1
    var title_template: String = "{title}"
    var content_template: String = "{title}"
    var strip_tags_mentions: Bool = true
    var title_exclusions: String = ""
    var translate_title_zh_cn: Bool = false
    var delete_after_publish: Bool = true

    enum CodingKeys: String, CodingKey {
        case id, settings_version, directories, account_id, interval_minutes, order, enabled, active_start, active_end
        case scope, guild_id, channel_id, feed_type, limit, title_template, content_template
        case strip_tags_mentions, title_exclusions, translate_title_zh_cn, delete_after_publish
    }

    init(
        id: String = UUID().uuidString,
        directories: [String],
        account_id: String = "",
        interval_minutes: Int,
        order: String,
        enabled: Bool = true,
        active_start: String = "",
        active_end: String = "",
        scope: String = "author_global",
        guild_id: String = "",
        channel_id: String = "",
        feed_type: Int = 1,
        limit: Int = 1,
        title_template: String = "{title}",
        content_template: String = "{title}",
        strip_tags_mentions: Bool = true,
        title_exclusions: String = "",
        translate_title_zh_cn: Bool = false,
        delete_after_publish: Bool = true
    ) {
        self.id = id
        self.directories = directories
        self.account_id = account_id
        self.interval_minutes = interval_minutes
        self.order = order
        self.enabled = enabled
        self.active_start = active_start
        self.active_end = active_end
        self.scope = scope
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.feed_type = feed_type
        self.limit = limit
        self.title_template = title_template
        self.content_template = content_template
        self.strip_tags_mentions = strip_tags_mentions
        self.title_exclusions = title_exclusions
        self.translate_title_zh_cn = translate_title_zh_cn
        self.delete_after_publish = delete_after_publish
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        id = try c.decodeIfPresent(String.self, forKey: .id) ?? UUID().uuidString
        settings_version = try c.decodeIfPresent(Int.self, forKey: .settings_version) ?? 0
        directories = try c.decodeIfPresent([String].self, forKey: .directories) ?? []
        account_id = try c.decodeIfPresent(String.self, forKey: .account_id) ?? ""
        interval_minutes = try c.decodeIfPresent(Int.self, forKey: .interval_minutes) ?? 60
        order = try c.decodeIfPresent(String.self, forKey: .order) ?? "sequential"
        enabled = try c.decodeIfPresent(Bool.self, forKey: .enabled) ?? true
        active_start = try c.decodeIfPresent(String.self, forKey: .active_start) ?? ""
        active_end = try c.decodeIfPresent(String.self, forKey: .active_end) ?? ""
        scope = try c.decodeIfPresent(String.self, forKey: .scope) ?? "author_global"
        guild_id = try c.decodeIfPresent(String.self, forKey: .guild_id) ?? ""
        channel_id = try c.decodeIfPresent(String.self, forKey: .channel_id) ?? ""
        feed_type = try c.decodeIfPresent(Int.self, forKey: .feed_type) ?? 1
        limit = try c.decodeIfPresent(Int.self, forKey: .limit) ?? 1
        title_template = try c.decodeIfPresent(String.self, forKey: .title_template) ?? "{title}"
        content_template = try c.decodeIfPresent(String.self, forKey: .content_template) ?? "{title}"
        strip_tags_mentions = try c.decodeIfPresent(Bool.self, forKey: .strip_tags_mentions) ?? true
        title_exclusions = try c.decodeIfPresent(String.self, forKey: .title_exclusions) ?? ""
        translate_title_zh_cn = try c.decodeIfPresent(Bool.self, forKey: .translate_title_zh_cn) ?? false
        delete_after_publish = try c.decodeIfPresent(Bool.self, forKey: .delete_after_publish) ?? true
    }
}

struct PublishHistoryEntry: Codable, Identifiable {
    var id: String { "\(content_id)-\(synced_at)" }
    var content_id: String
    var author: String
    var desc: String
    var output_path: String
    var feed_id: String
    var share_url: String
    var synced_at: String
    var status: String
    var error: String?

    var isPublishSuccess: Bool {
        status == "ok" && !share_url.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    var displayStatus: String {
        isPublishSuccess ? "ok" : "failed"
    }

    var displayError: String {
        if let error, !error.isEmpty { return error }
        return status == "ok" ? "发布后未返回分享链接" : "发布失败"
    }

    var displayTime: String {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        let date = formatter.date(from: synced_at) ?? {
            formatter.formatOptions = [.withInternetDateTime]
            return formatter.date(from: synced_at)
        }()
        guard let date else { return synced_at }
        let output = DateFormatter()
        output.locale = Locale(identifier: "zh_CN")
        output.timeZone = .current
        output.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return output.string(from: date)
    }
}

struct PublishHistoryFile: Codable {
    var entries: [PublishHistoryEntry]
}

struct VideoSource: Codable, Identifiable, Equatable {
    var id: UUID = UUID()
    var enabled: Bool = true
    var name: String = ""
    var source_url: String = ""
    var publish_scope: String = "author_global"
    var guild_id: String = ""
    var channel_id: String = ""
    var count: Int = 1
    var title_template: String = "{title}"
    var content_template: String = "{title}"
    var feed_type: Int = 1

    enum CodingKeys: String, CodingKey {
        case enabled, name, source_url, publish_scope, guild_id, channel_id, count, title_template, content_template, feed_type
    }
}

struct DownloadTaskProgress {
    var total: Int = 0
    var completed: Int = 0
    var skippedDuplicates: Int = 0
    var status: String = "等待下载"

    var fraction: Double {
        total > 0 ? min(1, Double(completed) / Double(total)) : (skippedDuplicates > 0 ? 1 : 0)
    }
}

enum SingleDownloadPhase {
    case idle
    case downloading
    case success
    case duplicate
    case failed
}

struct SingleDownloadProgress {
    var phase: SingleDownloadPhase = .idle
    var message: String = "等待下载"

    var canRedownload: Bool {
        phase == .success || phase == .duplicate
    }
}

enum DownloadMode: String, CaseIterable, Identifiable {
    case single
    case profiles

    var id: String { rawValue }
    var title: String { self == .single ? "单视频下载" : "主页批量下载" }
    var icon: String { self == .single ? "link" : "person.2.crop.square.stack" }
}

enum PublishMode: String, CaseIterable, Identifiable {
    case single
    case scheduled
    case history

    var id: String { rawValue }
    var title: String {
        switch self {
        case .single: "单次发布"
        case .scheduled: "定时发布"
        case .history: "发布记录"
        }
    }
    var icon: String {
        switch self {
        case .single: "paperplane.circle"
        case .scheduled: "clock"
        case .history: "clock.arrow.circlepath"
        }
    }
}

struct ProfileParseResponse: Codable {
    var ok: Bool
    var url: String
    var name: String
    var first_video_url: String
    var error: String
}

struct TencentStatusResponse: Codable {
    var ok: Bool
    var logged_in: Bool
    var token_source: String
    var nickname: String
    var global_nickname: String
    var is_guild_author: Bool
    var error: String
}

struct TencentCLIStatus: Codable {
    var success: Bool
    var data: TencentCLIStatusData
}

struct TencentCLIStatusData: Codable {
    var tokenSource: String?
    var valid: Bool?
    var isLoggedIn: Bool?
}

struct TencentCLIUser: Codable {
    var success: Bool
    var data: TencentCLIUserData
}

struct TencentCLIUserData: Codable {
    var nickname: String?
    var global_nickname: String?
    var is_guild_author: Bool?
}

enum WorkspaceSection: String, CaseIterable, Identifiable {
    case download
    case publish
    case log

    var id: String { rawValue }
    var title: String {
        switch self {
        case .download: "下载"
        case .publish: "发布"
        case .log: "日志"
        }
    }
    var icon: String {
        switch self {
        case .download: "arrow.down.circle"
        case .publish: "paperplane.circle"
        case .log: "terminal"
        }
    }
}

final class AppModel: ObservableObject {
    @Published var config = SchedulerConfig()
    @Published var logs: String = ""
    @Published var logLineCount: Int = 0
    @Published var droppedLogLineCount: Int = 0
    @Published var status: String = "准备就绪"
    @Published var schedulerRunning = false
    @Published var busy = false
    @Published var tencentTokenInput: String = ""
    @Published var tencentStatusText: String = "未检查"
    @Published var tencentStatusOK = false
    @Published var tencentNickname: String = ""
    @Published var tencentAccountNameInput: String = ""
    @Published var profileProgress: [String: DownloadTaskProgress] = [:]
    @Published var singleDownloadProgress = SingleDownloadProgress()
    @Published var noticeText: String = ""
    @Published var noticeIsError = false
    @Published var publishHistory: [PublishHistoryEntry] = []
    @Published var youtubeCookieStatusText: String = ""
    @Published var schedulerNow = Date()
    @Published var historyRedownloadStatus: [String: String] = [:]
    @Published var updateStatusText: String = "未检查更新"
    @Published var updateAvailable = false
    @Published var latestVersion: String = ""
    @Published var latestReleaseURL: URL = appReleasePageURL
    @Published var checkingUpdate = false

    let appRoot: URL
    let configURL: URL
    let logDirectoryURL: URL
    let logFileURL: URL
    private var schedulerProcess: Process?
    private var schedulerTimer: Timer?
    private var activeGenericProcess: Process?
    private var genericProcessOutput = ""
    private var singleProcessOutput = ""
    private var profileDownloadProcesses: [String: Process] = [:]
    private var profileProcessOutputs: [String: String] = [:]
    private var scheduledDownloadTaskIDsByProfile: [String: String] = [:]
    private var completedDownloadJobsByProfile: [String: Set<Int>] = [:]
    private var lastScheduledRuns: [String: Date] = [:]
    private var nextPublishDirectoryIndexes: [String: Int] = [:]
    private var publishProcesses: [String: Process] = [:]
    private var publishProcessOutputs: [String: String] = [:]
    private var historyRedownloadProcesses: [String: Process] = [:]
    private var historyRedownloadOutputs: [String: String] = [:]
    private var suppressNextTencentFailureNotice = false
    private var didAutoCheckUpdate = false
    private var logLines: [String] = []
    private let maxVisibleLogLines = 100
    private let maxVisibleLogLineLength = 1200

    var hasActiveProfileDownloads: Bool {
        !profileDownloadProcesses.isEmpty
    }

    var hasActiveWork: Bool {
        busy || hasActiveProfileDownloads || publishProcesses.values.contains(where: \.isRunning)
    }

    init() {
        let bundleURL = Bundle.main.bundleURL
        self.appRoot = bundleURL.deletingLastPathComponent().deletingLastPathComponent()
        let supportRoot = URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent("Library/Application Support/Videocp Studio")
        try? FileManager.default.createDirectory(at: supportRoot, withIntermediateDirectories: true)
        self.configURL = supportRoot.appendingPathComponent("mac-app.json")
        self.logDirectoryURL = supportRoot.appendingPathComponent("logs")
        self.logFileURL = logDirectoryURL.appendingPathComponent("app.log")
        try? FileManager.default.createDirectory(at: logDirectoryURL, withIntermediateDirectories: true)
        let legacyConfigURL = appRoot.appendingPathComponent("mac-app.json")
        if !FileManager.default.fileExists(atPath: configURL.path),
           FileManager.default.fileExists(atPath: legacyConfigURL.path) {
            try? FileManager.default.copyItem(at: legacyConfigURL, to: configURL)
            try? FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: configURL.path)
        }
        load()
        migrateLegacyTencentAccount()
        validateBundledRuntime()
        loadPublishHistory()
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.7) { [weak self] in
            self?.checkTencentChannel(silent: true)
        }
        startSchedulerMonitor()
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) { [weak self] in
            self?.checkForUpdates(silent: true)
        }
    }

    func load() {
        do {
            if !FileManager.default.fileExists(atPath: configURL.path) {
                save()
            }
            let data = try Data(contentsOf: configURL)
            config = try JSONDecoder().decode(SchedulerConfig.self, from: data)
            if migrateLegacyAutomation() {
                save()
            } else {
                try mirrorRuntimeConfig(data)
            }
            status = "已加载配置"
            appendLog("已加载配置 \(configURL.path)")
        } catch {
            status = "配置读取失败"
            appendLog("配置读取失败: \(error.localizedDescription)")
        }
    }

    private func migrateLegacyAutomation() -> Bool {
        var migrated = false
        if config.automation.download_tasks.isEmpty,
           config.automation.download_enabled,
           !config.automation.download_profile_id.isEmpty {
            config.automation.download_tasks.append(
                ScheduledDownloadTask(
                    profile_id: config.automation.download_profile_id,
                    interval_minutes: max(1, config.automation.download_interval_minutes)
                )
            )
            config.automation.download_enabled = false
            migrated = true
        }
        if config.automation.publish_tasks.isEmpty,
           config.automation.publish_enabled,
           !config.automation.publish_directories.isEmpty {
            config.automation.publish_tasks.append(
                ScheduledPublishTask(
                    directories: config.automation.publish_directories,
                    interval_minutes: max(1, config.automation.publish_interval_minutes),
                    order: config.automation.publish_order,
                    scope: config.publish.scope,
                    guild_id: config.publish.guild_id,
                    channel_id: config.publish.channel_id,
                    feed_type: config.publish.feed_type,
                    limit: config.publish.limit,
                    title_template: config.publish.title_template,
                    content_template: config.publish.content_template,
                    strip_tags_mentions: config.publish.strip_tags_mentions,
                    title_exclusions: config.publish.title_exclusions,
                    translate_title_zh_cn: config.publish.translate_title_zh_cn,
                    delete_after_publish: config.publish.delete_after_publish
                )
            )
            config.automation.publish_enabled = false
            migrated = true
        }
        for index in config.automation.download_tasks.indices {
            if config.automation.download_tasks[index].active_start.isEmpty {
                config.automation.download_tasks[index].active_start = config.active_start
                migrated = true
            }
            if config.automation.download_tasks[index].active_end.isEmpty {
                config.automation.download_tasks[index].active_end = config.active_end
                migrated = true
            }
        }
        for index in config.automation.publish_tasks.indices {
            if config.automation.publish_tasks[index].active_start.isEmpty {
                config.automation.publish_tasks[index].active_start = config.active_start
                migrated = true
            }
            if config.automation.publish_tasks[index].active_end.isEmpty {
                config.automation.publish_tasks[index].active_end = config.active_end
                migrated = true
            }
            if config.automation.publish_tasks[index].settings_version < 1 {
                config.automation.publish_tasks[index].settings_version = 1
                config.automation.publish_tasks[index].scope = config.publish.scope
                config.automation.publish_tasks[index].guild_id = config.publish.guild_id
                config.automation.publish_tasks[index].channel_id = config.publish.channel_id
                config.automation.publish_tasks[index].feed_type = config.publish.feed_type
                config.automation.publish_tasks[index].limit = config.publish.limit
                config.automation.publish_tasks[index].title_template = config.publish.title_template
                config.automation.publish_tasks[index].content_template = config.publish.content_template
                config.automation.publish_tasks[index].strip_tags_mentions = config.publish.strip_tags_mentions
                config.automation.publish_tasks[index].title_exclusions = config.publish.title_exclusions
                config.automation.publish_tasks[index].translate_title_zh_cn = config.publish.translate_title_zh_cn
                config.automation.publish_tasks[index].delete_after_publish = config.publish.delete_after_publish
                migrated = true
            }
        }
        return migrated
    }

    func save() {
        do {
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
            let data = try encoder.encode(config)
            try data.write(to: configURL, options: .atomic)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: configURL.path)
            try mirrorRuntimeConfig(data)
            status = "已保存配置"
        } catch {
            status = "保存失败"
            appendLog("保存失败: \(error.localizedDescription)")
            reportIssue("配置保存失败：\(error.localizedDescription)")
        }
    }

    func reportIssue(_ message: String) {
        noticeText = message
        noticeIsError = true
    }

    func reportInfo(_ message: String) {
        noticeText = message
        noticeIsError = false
    }

    func dismissNotice() {
        noticeText = ""
    }

    func checkForUpdates(silent: Bool = false) {
        if silent && didAutoCheckUpdate { return }
        if silent { didAutoCheckUpdate = true }
        guard !checkingUpdate else { return }
        checkingUpdate = true
        updateStatusText = "正在检查更新"

        var request = URLRequest(url: appReleaseAPIURL)
        request.timeoutInterval = 12
        request.setValue("application/vnd.github+json", forHTTPHeaderField: "Accept")
        request.setValue("Videocp-Studio/\(appVersion)", forHTTPHeaderField: "User-Agent")

        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            DispatchQueue.main.async {
                guard let self else { return }
                self.checkingUpdate = false
                if let error {
                    self.updateStatusText = "检查更新失败"
                    if !silent {
                        self.reportIssue("检查更新失败：\(error.localizedDescription)")
                    }
                    return
                }
                guard let http = response as? HTTPURLResponse, (200..<300).contains(http.statusCode),
                      let data,
                      let release = try? JSONDecoder().decode(GitHubReleaseResponse.self, from: data) else {
                    self.updateStatusText = "检查更新失败"
                    if !silent {
                        self.reportIssue("检查更新失败：无法读取 GitHub Release 信息")
                    }
                    return
                }

                let latest = release.tag_name.trimmingCharacters(in: .whitespacesAndNewlines)
                let normalizedLatest = self.normalizedVersion(latest)
                self.latestVersion = normalizedLatest
                self.latestReleaseURL = URL(string: release.html_url) ?? appReleasePageURL

                if self.isVersion(normalizedLatest, newerThan: appVersion) {
                    self.updateAvailable = true
                    self.updateStatusText = "发现新版本 \(normalizedLatest)"
                    self.reportInfo("发现新版本 \(normalizedLatest)，可以点击“打开更新”下载。")
                } else {
                    self.updateAvailable = false
                    self.updateStatusText = "已是最新版"
                    if !silent {
                        self.reportInfo("当前已是最新版 \(appVersion)")
                    }
                }
            }
        }.resume()
    }

    func openLatestRelease() {
        NSWorkspace.shared.open(latestReleaseURL)
    }

    private func normalizedVersion(_ value: String) -> String {
        value.trimmingCharacters(in: .whitespacesAndNewlines)
            .trimmingCharacters(in: CharacterSet(charactersIn: "vV"))
    }

    private func isVersion(_ candidate: String, newerThan current: String) -> Bool {
        let left = versionParts(candidate)
        let right = versionParts(current)
        for index in 0..<max(left.count, right.count) {
            let lvalue = index < left.count ? left[index] : 0
            let rvalue = index < right.count ? right[index] : 0
            if lvalue != rvalue {
                return lvalue > rvalue
            }
        }
        return false
    }

    private func versionParts(_ value: String) -> [Int] {
        normalizedVersion(value)
            .split(separator: ".")
            .map { part in
                let digits = part.prefix { $0.isNumber }
                return Int(digits) ?? 0
            }
    }

    func chooseDownloadDirectory() {
        if let path = chooseDirectory() {
            config.download.output_dir = path
            if config.publish.input_dir.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || config.publish.input_dir == "./downloads" {
                config.publish.input_dir = path
            }
            save()
        }
    }

    func chooseYouTubeCookieFile() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.plainText]
        if panel.runModal() == .OK, let path = panel.url?.path {
            config.download.youtube_cookies_path = path
            save()
        }
    }

    func saveYouTubeCookies() {
        let text = config.download.youtube_cookies_text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else {
            youtubeCookieStatusText = "请先粘贴 cookies.txt 内容"
            reportIssue("请先粘贴 YouTube cookies.txt 内容")
            return
        }
        config.download.youtube_cookies_path = ""
        save()
        youtubeCookieStatusText = "Cookie 已保存并将在下次下载生效"
        reportInfo("YouTube Cookie 已保存生效")
    }

    func choosePublishDirectory() {
        if let path = chooseDirectory() {
            config.publish.input_dir = path
            save()
        }
    }

    func choosePublishVideo() {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = false
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = false
        panel.allowedContentTypes = [.mpeg4Movie, .movie]
        if panel.runModal() == .OK, let path = panel.url?.path {
            config.publish.input_video = path
            config.publish.input_dir = panel.url?.deletingLastPathComponent().path ?? ""
            save()
        }
    }

    func addScheduledDownloadTask(profileID: String, intervalMinutes: Int, activeStart: String, activeEnd: String) {
        guard !profileID.isEmpty else { return }
        config.automation.download_tasks.append(
            ScheduledDownloadTask(
                profile_id: profileID,
                interval_minutes: max(1, intervalMinutes),
                active_start: normalizedWallTime(activeStart, fallback: "09:00"),
                active_end: normalizedWallTime(activeEnd, fallback: "23:00")
            )
        )
        save()
        startSchedulerMonitor()
    }

    func deleteScheduledDownloadTask(_ task: ScheduledDownloadTask) {
        if scheduledDownloadTaskIDsByProfile[task.profile_id] == task.id,
           let process = profileDownloadProcesses[task.profile_id],
           process.isRunning {
            process.terminate()
        }
        config.automation.download_tasks.removeAll { $0.id == task.id }
        lastScheduledRuns.removeValue(forKey: task.id)
        save()
    }

    func addScheduledPublishTask(_ task: ScheduledPublishTask) {
        let directories = task.directories
        guard !directories.isEmpty else { return }
        var normalized = task
        normalized.interval_minutes = max(1, task.interval_minutes)
        normalized.active_start = normalizedWallTime(task.active_start, fallback: "09:00")
        normalized.active_end = normalizedWallTime(task.active_end, fallback: "23:00")
        normalized.limit = max(1, task.limit)
        normalized.settings_version = 1
        config.automation.publish_tasks.append(normalized)
        save()
        startSchedulerMonitor()
    }

    func deleteScheduledPublishTask(_ task: ScheduledPublishTask) {
        if let process = publishProcesses[task.id], process.isRunning {
            process.terminate()
        }
        config.automation.publish_tasks.removeAll { $0.id == task.id }
        lastScheduledRuns.removeValue(forKey: task.id)
        nextPublishDirectoryIndexes.removeValue(forKey: task.id)
        save()
    }

    func updateScheduledDownloadTask(_ task: ScheduledDownloadTask) {
        guard let index = config.automation.download_tasks.firstIndex(where: { $0.id == task.id }) else { return }
        config.automation.download_tasks[index].interval_minutes = max(1, task.interval_minutes)
        config.automation.download_tasks[index].active_start = normalizedWallTime(task.active_start, fallback: "09:00")
        config.automation.download_tasks[index].active_end = normalizedWallTime(task.active_end, fallback: "23:00")
        save()
        reportInfo("定时下载任务已更新")
    }

    func updateScheduledPublishTask(_ task: ScheduledPublishTask) {
        guard let index = config.automation.publish_tasks.firstIndex(where: { $0.id == task.id }) else { return }
        var normalized = task
        normalized.interval_minutes = max(1, task.interval_minutes)
        normalized.active_start = normalizedWallTime(task.active_start, fallback: "09:00")
        normalized.active_end = normalizedWallTime(task.active_end, fallback: "23:00")
        normalized.limit = max(1, task.limit)
        normalized.settings_version = 1
        config.automation.publish_tasks[index] = normalized
        save()
        reportInfo("定时发布任务已更新")
    }

    func setScheduledDownloadTaskEnabled(_ task: ScheduledDownloadTask, enabled: Bool) {
        guard let index = config.automation.download_tasks.firstIndex(where: { $0.id == task.id }) else { return }
        config.automation.download_tasks[index].enabled = enabled
        lastScheduledRuns.removeValue(forKey: task.id)
        save()
        appendLog("\(enabled ? "已开启" : "已停止")定时下载: \(task.profile_id)")
        if !enabled,
           scheduledDownloadTaskIDsByProfile[task.profile_id] == task.id,
           let process = profileDownloadProcesses[task.profile_id],
           process.isRunning {
            process.terminate()
        }
        startSchedulerMonitor()
        if enabled {
            runScheduledTasksIfNeeded(forceTaskID: task.id)
        }
    }

    func setScheduledPublishTaskEnabled(_ task: ScheduledPublishTask, enabled: Bool) {
        guard let index = config.automation.publish_tasks.firstIndex(where: { $0.id == task.id }) else { return }
        config.automation.publish_tasks[index].enabled = enabled
        lastScheduledRuns.removeValue(forKey: task.id)
        save()
        appendLog("\(enabled ? "已开启" : "已停止")定时发布任务")
        if !enabled, let process = publishProcesses[task.id], process.isRunning {
            process.terminate()
        }
        startSchedulerMonitor()
        if enabled {
            runScheduledTasksIfNeeded(forceTaskID: task.id)
        }
    }

    func chooseAutomationDirectory() -> String? { chooseDirectory() }

    func chooseSkillDirectory() {
        if let path = chooseDirectory() {
            config.publish.skill_dir = path
            config.sync.skill_dir = path
            save()
        }
    }

    func openDownloadDirectory() {
        guard requireDownloadDirectory() else { return }
        openPath(config.download.output_dir)
    }
    func openPublishDirectory() { openPath(config.publish.input_dir) }

    func openPathForPublishVideo() {
        let path = config.publish.input_video.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !path.isEmpty else {
            reportIssue("请先选择视频")
            return
        }
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
    }

    var downloadDirectoryReady: Bool {
        let path = config.download.output_dir.trimmingCharacters(in: .whitespacesAndNewlines)
        return !path.isEmpty
    }

    var downloadDirectoryLabel: String {
        let path = config.download.output_dir.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !path.isEmpty else { return "未选择" }
        return URL(fileURLWithPath: (path as NSString).expandingTildeInPath).lastPathComponent
    }

    private func requireDownloadDirectory() -> Bool {
        guard downloadDirectoryReady else {
            reportIssue("请先选择视频保存位置")
            appendLog("请先选择视频保存位置")
            return false
        }
        return true
    }

    func resetSingleDownloadProgress() {
        singleDownloadProgress = SingleDownloadProgress()
    }

    func runSingleDownload(forceRedownload: Bool = false) {
        guard requireDownloadDirectory() else { return }
        let url = config.download.single_video_url.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !url.isEmpty else {
            appendLog("请先填写单视频链接")
            reportIssue("请先填写单视频链接")
            return
        }
        guard !busy else {
            appendLog("已有任务在运行")
            reportIssue("已有单视频任务或配置检查正在运行")
            return
        }
        config.download.inputs_text = url
        save()
        singleDownloadProgress = SingleDownloadProgress(
            phase: .downloading,
            message: forceRedownload ? "正在重新下载" : "正在下载"
        )
        appendLog(forceRedownload ? "开始重新下载单视频" : "开始下载单视频")
        busy = true
        singleProcessOutput = ""
        var arguments = ["app-download", "--app-config", configURL.path]
        if forceRedownload {
            arguments.append("--force-redownload")
        }
        let process = makeProcess(arguments: arguments)
        streamSingleDownload(process)
        do {
            try process.run()
        } catch {
            busy = false
            singleDownloadProgress = SingleDownloadProgress(phase: .failed, message: "启动失败")
            appendLog("命令启动失败: \(error.localizedDescription)")
            reportIssue("下载启动失败：\(error.localizedDescription)")
        }
    }

    @discardableResult
    func runProfileDownload(_ profile: DownloadProfile, scheduleTaskID: String? = nil) -> Bool {
        guard requireDownloadDirectory() else { return false }
        guard !isProfileDownloading(profile.id) else {
            appendLog("主页下载已在运行: \(profile.name.isEmpty ? profile.url : profile.name)")
            reportIssue("这个主页正在下载中")
            return false
        }
        guard !profile.url.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            appendLog("主页 URL 为空")
            reportIssue("主页 URL 为空，请重新添加")
            return false
        }
        save()
        completedDownloadJobsByProfile[profile.id] = []
        profileProcessOutputs[profile.id] = ""
        profileProgress[profile.id] = DownloadTaskProgress(total: max(1, profile.count), completed: 0, status: "准备下载")
        appendLog("开始下载主页: \(profile.name.isEmpty ? profile.url : profile.name)")
        do {
            let snapshotURL = try writeProfileDownloadSnapshot(profile)
            let process = makeProcess(arguments: ["app-download", "--app-config", snapshotURL.path])
            profileDownloadProcesses[profile.id] = process
            scheduledDownloadTaskIDsByProfile[profile.id] = scheduleTaskID
            streamProfileDownload(process, profileID: profile.id, snapshotURL: snapshotURL)
            try process.run()
            return true
        } catch {
            profileDownloadProcesses.removeValue(forKey: profile.id)
            scheduledDownloadTaskIDsByProfile.removeValue(forKey: profile.id)
            completedDownloadJobsByProfile.removeValue(forKey: profile.id)
            profileProcessOutputs.removeValue(forKey: profile.id)
            profileProgress[profile.id]?.status = "启动失败"
            appendLog("主页下载启动失败: \(error.localizedDescription)")
            reportIssue("主页下载启动失败：\(error.localizedDescription)")
            return false
        }
    }

    func stopProfileDownload(_ profile: DownloadProfile) {
        guard let process = profileDownloadProcesses[profile.id], process.isRunning else { return }
        profileProgress[profile.id]?.status = "正在停止"
        process.terminate()
        reportInfo("正在停止主页下载：\(profile.name.isEmpty ? profile.url : profile.name)")
    }

    func deleteProfile(_ profile: DownloadProfile) {
        config.download.profiles.removeAll { $0.id == profile.id }
        profileProgress.removeValue(forKey: profile.id)
        save()
        appendLog("已删除主页: \(profile.name.isEmpty ? profile.url : profile.name)")
    }

    func parseProfileDraft() {
        let urls = profileDraftURLs()
        guard !urls.isEmpty else {
            appendLog("请先填写主页 URL")
            reportIssue("请先填写主页 URL")
            return
        }
        guard !busy else {
            appendLog("已有任务在运行")
            reportIssue("已有单视频任务或配置检查正在运行")
            return
        }
        save()
        busy = true
        status = urls.count > 1 ? "正在批量解析主页" : "正在解析主页"
        appendLog(urls.count > 1 ? "批量解析主页: \(urls.count) 个" : "解析主页: \(urls[0])")
        DispatchQueue.global(qos: .userInitiated).async {
            var succeeded = 0
            var failed = 0
            for (index, url) in urls.enumerated() {
                DispatchQueue.main.sync {
                    self.status = "正在解析主页 \(index + 1)/\(urls.count)"
                    self.appendLog("解析主页: \(url)")
                }
                let process = self.makeProcess(arguments: ["app-parse-profile", "--app-config", self.configURL.path, "--url", url])
                let pipe = Pipe()
                process.standardOutput = pipe
                process.standardError = pipe
                do {
                    try process.run()
                    process.waitUntilExit()
                    let data = pipe.fileHandleForReading.readDataToEndOfFile()
                    let text = String(data: data, encoding: .utf8) ?? ""
                    var ok = false
                    DispatchQueue.main.sync {
                        ok = self.handleProfileParseOutput(text, fallbackURL: url, clearDraft: false)
                    }
                    if process.terminationStatus == 0 && ok {
                        succeeded += 1
                    } else {
                        failed += 1
                    }
                } catch {
                    failed += 1
                    DispatchQueue.main.sync {
                        self.appendLog("解析启动失败: \(url) \(error.localizedDescription)")
                        self.reportIssue("主页解析启动失败：\(error.localizedDescription)")
                    }
                }
            }
            DispatchQueue.main.async {
                self.busy = false
                self.config.download.profile_url_draft = ""
                self.save()
                if failed == 0 {
                    self.status = "主页解析完成"
                    self.reportInfo("已添加 \(succeeded) 个 UP 主")
                } else {
                    self.status = "部分主页解析失败"
                    self.reportIssue("已添加 \(succeeded) 个 UP 主，\(failed) 个解析失败")
                }
            }
        }
    }

    private func profileDraftURLs() -> [String] {
        let raw = config.download.profile_url_draft
        var seen: Set<String> = []
        return raw
            .split(whereSeparator: \.isNewline)
            .map { String($0).trimmingCharacters(in: .whitespacesAndNewlines) }
            .filter { !$0.isEmpty }
            .filter { value in
                if seen.contains(value) { return false }
                seen.insert(value)
                return true
            }
    }

    @discardableResult
    private func handleProfileParseOutput(_ text: String, fallbackURL: String, clearDraft: Bool = true) -> Bool {
        let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
        let jsonText: String
        if let start = trimmed.firstIndex(of: "{"), let end = trimmed.lastIndex(of: "}") {
            jsonText = String(trimmed[start...end])
        } else {
            jsonText = trimmed
        }
        guard let data = jsonText.data(using: .utf8),
              let response = try? JSONDecoder().decode(ProfileParseResponse.self, from: data) else {
            appendLog("主页解析返回异常: \(trimmed)")
            reportIssue("主页解析返回异常，请检查网络或重新安装 App")
            return false
        }
        guard response.ok else {
            appendLog("主页解析失败: \(response.error)")
            reportIssue("主页解析失败：\(response.error)")
            return false
        }
        let name = response.name.isEmpty ? fallbackURL : response.name
        var profile = DownloadProfile(
            name: name,
            url: response.url.isEmpty ? fallbackURL : response.url,
            first_video_url: response.first_video_url,
            order: config.download.order,
            quality: supportsQualitySelection(for: response.url.isEmpty ? fallbackURL : response.url)
                ? config.download.quality
                : "best",
            count: max(1, config.download.count),
            parsed_at: ISO8601DateFormatter().string(from: Date())
        )
        if platformName(for: profile.url) == "小红书" {
            profile.order = "latest"
        }
        if let index = config.download.profiles.firstIndex(where: { $0.url == profile.url }) {
            let existing = config.download.profiles[index]
            profile.id = existing.id
            profile.name = existing.name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? profile.name : existing.name
            profile.order = existing.order
            profile.quality = existing.quality
            profile.count = existing.count
            config.download.profiles[index] = profile
            appendLog("已更新主页卡片: \(profile.name)")
        } else {
            config.download.profiles.append(profile)
            appendLog("已添加主页卡片: \(name)")
        }
        if clearDraft {
            config.download.profile_url_draft = ""
        }
        save()
        reportInfo("已添加 UP 主：\(profile.name)")
        return true
    }

    private func chooseDirectory() -> String? {
        let panel = NSOpenPanel()
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.canCreateDirectories = true
        panel.allowsMultipleSelection = false
        return panel.runModal() == .OK ? panel.url?.path : nil
    }

    private func openPath(_ value: String) {
        let expanded = (value as NSString).expandingTildeInPath
        let url: URL
        if expanded.hasPrefix("/") {
            url = URL(fileURLWithPath: expanded)
        } else {
            url = appRoot.appendingPathComponent(expanded)
        }
        NSWorkspace.shared.open(url)
    }

    func runDownload() {
        save()
        appendLog("开始下载")
        runProcess(arguments: ["app-download", "--app-config", configURL.path])
    }

    func checkYouTubeHelper() {
        appendLog("检查 YouTube 下载设置")
        runProcess(arguments: ["app-youtube-setup"])
    }

    func setupTencentChannel() {
        save()
        suppressNextTencentFailureNotice = false
        let token = tencentTokenInput.trimmingCharacters(in: .whitespacesAndNewlines)
        appendLog(token.isEmpty ? "检查腾讯频道配置" : "保存并验证腾讯频道 Token")
        runTencentStatus(arguments: ["app-tencent-setup", "--json"], extraEnvironment: token.isEmpty ? [:] : ["QQ_AI_CONNECT_TOKEN_INPUT": token])
    }

    func addTencentAccount() {
        let token = tencentTokenInput.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !token.isEmpty else {
            reportIssue("请先粘贴频道 Token")
            return
        }
        guard !busy else {
            reportIssue("已有任务正在运行")
            return
        }
        busy = true
        tencentStatusText = "正在验证"
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                let statusOutput = try self.runTencentCLI(["login", "status", "--json"], token: token)
                let status = try JSONDecoder().decode(TencentCLIStatus.self, from: Data(statusOutput.utf8))
                guard status.success && (status.data.valid == true || status.data.isLoggedIn == true) else {
                    throw NSError(domain: "VideocpStudio", code: 1, userInfo: [NSLocalizedDescriptionKey: "Token 未通过登录验证"])
                }
                let userOutput = try self.runTencentCLI(["manage", "get-user-info", "--json"], token: token)
                let user = try JSONDecoder().decode(TencentCLIUser.self, from: Data(userOutput.utf8))
                let nickname = user.data.nickname ?? user.data.global_nickname ?? ""
                let author = user.data.is_guild_author ?? false
                DispatchQueue.main.async {
                    let requestedName = self.tencentAccountNameInput.trimmingCharacters(in: .whitespacesAndNewlines)
                    let account = TencentAccount(
                        name: requestedName.isEmpty ? nickname : requestedName,
                        token: token,
                        nickname: nickname,
                        is_guild_author: author,
                        verified: true
                    )
                    self.config.tencent_accounts.append(account)
                    self.config.publish.account_id = account.id
                    self.tencentTokenInput = ""
                    self.tencentAccountNameInput = ""
                    self.tencentStatusOK = true
                    self.tencentNickname = account.displayName
                    self.tencentStatusText = "\(account.displayName) · \(author ? "创作者" : "非创作者")"
                    self.busy = false
                    self.save()
                    self.reportInfo("频道账号已添加：\(account.displayName)")
                }
            } catch {
                DispatchQueue.main.async {
                    self.busy = false
                    self.tencentStatusOK = false
                    self.tencentStatusText = "验证失败"
                    self.reportIssue("频道账号添加失败：\(error.localizedDescription)")
                }
            }
        }
    }

    func deleteTencentAccount(_ account: TencentAccount) {
        let credential = configURL.deletingLastPathComponent()
            .appendingPathComponent("accounts")
            .appendingPathComponent("\(account.id).env")
        try? FileManager.default.removeItem(at: credential)
        config.tencent_accounts.removeAll { $0.id == account.id }
        if config.publish.account_id == account.id {
            config.publish.account_id = config.tencent_accounts.first?.id ?? ""
        }
        for index in config.automation.publish_tasks.indices where config.automation.publish_tasks[index].account_id == account.id {
            config.automation.publish_tasks[index].account_id = ""
            config.automation.publish_tasks[index].enabled = false
        }
        save()
        reportInfo("已删除频道账号：\(account.displayName)")
    }

    func tokenForAccount(_ accountID: String) -> String {
        if let token = config.tencent_accounts.first(where: { $0.id == accountID })?.token, !token.isEmpty {
            return token
        }
        return legacyTencentToken()
    }

    private func credentialURL(for accountID: String, token: String) throws -> URL {
        let directory = configURL.deletingLastPathComponent().appendingPathComponent("accounts", isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        let safeID = accountID.replacingOccurrences(
            of: "[^A-Za-z0-9._-]",
            with: "-",
            options: .regularExpression
        )
        let url = directory.appendingPathComponent("\(safeID).env")
        try "QQ_AI_CONNECT_TOKEN=\(token)\n".write(to: url, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: url.path)
        return url
    }

    private func credentialEnvironment(for accountID: String) throws -> [String: String] {
        let token = tokenForAccount(accountID)
        guard !token.isEmpty else {
            throw NSError(domain: "VideocpStudio", code: 1, userInfo: [NSLocalizedDescriptionKey: "频道账号 Token 不存在"])
        }
        let url = try credentialURL(for: accountID, token: token)
        return ["QQ_AI_CONNECT_DOTENV": url.path]
    }

    private func legacyTencentToken() -> String {
        let envURL = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(".qqcli/.env")
        guard let text = try? String(contentsOf: envURL, encoding: .utf8) else { return "" }
        guard let line = text.split(separator: "\n")
            .map(String.init)
            .first(where: { $0.hasPrefix("QQ_AI_CONNECT_TOKEN=") }) else { return "" }
        return String(line.dropFirst("QQ_AI_CONNECT_TOKEN=".count))
    }

    private func migrateLegacyTencentAccount() {
        var changed = false
        for index in config.tencent_accounts.indices
        where config.tencent_accounts[index].name == "原有频道账号" {
            config.tencent_accounts[index].name = ""
            changed = true
        }
        if !config.tencent_accounts.isEmpty {
            if changed { save() }
            return
        }
        let token = legacyTencentToken()
        guard !token.isEmpty else { return }
        let account = TencentAccount(name: "", token: token, verified: true)
        config.tencent_accounts = [account]
        config.publish.account_id = account.id
        for index in config.automation.publish_tasks.indices where config.automation.publish_tasks[index].account_id.isEmpty {
            config.automation.publish_tasks[index].account_id = account.id
        }
        save()
    }

    func checkTencentChannel(silent: Bool = false) {
        if silent && busy { return }
        suppressNextTencentFailureNotice = silent
        appendLog("检查腾讯频道登录状态")
        runTencentStatus(arguments: ["app-tencent-setup", "--check", "--json"])
    }

    func runPublish() {
        save()
        guard publishProcesses["manual"]?.isRunning != true else {
            reportIssue("发布任务正在运行，请等待当前任务完成")
            return
        }
        let videoPath = config.publish.input_video.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !videoPath.isEmpty, FileManager.default.isReadableFile(atPath: videoPath) else {
            reportIssue("请先选择要发布的 MP4 视频")
            return
        }
        guard !config.publish.account_id.isEmpty, !tokenForAccount(config.publish.account_id).isEmpty else {
            reportIssue("请先选择一个已验证的频道账号")
            return
        }
        let directory = URL(fileURLWithPath: videoPath).deletingLastPathComponent().path
        appendLog("开始发布")
        let task = ScheduledPublishTask(
            id: "manual",
            directories: [directory],
            account_id: config.publish.account_id,
            interval_minutes: 1,
            order: "sequential",
            scope: config.publish.scope,
            guild_id: config.publish.guild_id,
            channel_id: config.publish.channel_id,
            feed_type: config.publish.feed_type,
            limit: config.publish.limit,
            title_template: config.publish.title_template,
            content_template: config.publish.content_template,
            strip_tags_mentions: config.publish.strip_tags_mentions,
            title_exclusions: config.publish.title_exclusions,
            translate_title_zh_cn: config.publish.translate_title_zh_cn,
            delete_after_publish: config.publish.delete_after_publish
        )
        runScheduledPublish(task, directory: directory, retryVideoPath: videoPath)
    }

    private func runScheduledPublish(_ task: ScheduledPublishTask, directory: String, retryVideoPath: String = "") {
        guard publishProcesses[task.id]?.isRunning != true else { return }
        guard !task.account_id.isEmpty else {
            reportIssue("发布任务未选择频道账号")
            return
        }
        let token = tokenForAccount(task.account_id)
        guard !token.isEmpty else {
            reportIssue("发布任务未选择有效的频道账号")
            return
        }
        do {
            let snapshotURL = try writeScheduledPublishSnapshot(task, directory: directory, retryVideoPath: retryVideoPath)
            let process = makeProcess(
                arguments: ["app-publish", "--app-config", snapshotURL.path],
                extraEnvironment: try credentialEnvironment(for: task.account_id)
            )
            publishProcesses[task.id] = process
            publishProcessOutputs[task.id] = ""
            streamScheduledPublish(process, taskID: task.id, snapshotURL: snapshotURL)
            try process.run()
        } catch {
            publishProcesses.removeValue(forKey: task.id)
            publishProcessOutputs.removeValue(forKey: task.id)
            reportIssue("定时发布启动失败：\(error.localizedDescription)")
        }
    }

    func retryPublish(_ entry: PublishHistoryEntry) {
        let path = entry.output_path.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !path.isEmpty else {
            reportIssue("这条失败记录没有本地视频路径，无法重新发布")
            return
        }
        let expanded = (path as NSString).expandingTildeInPath
        guard FileManager.default.isReadableFile(atPath: expanded) else {
            reportIssue("本地视频不存在，无法重新发布：\(expanded)")
            return
        }
        let retryID = "retry-\(entry.id.stableIDComponent)"
        guard publishProcesses[retryID]?.isRunning != true else {
            reportIssue("这条视频正在重新发布")
            return
        }
        do {
            let videoURL = URL(fileURLWithPath: expanded)
            let directory = videoURL.deletingLastPathComponent().path
            let task = ScheduledPublishTask(
                id: retryID,
                directories: [directory],
                account_id: config.publish.account_id,
                interval_minutes: 1,
                order: "sequential",
                scope: config.publish.scope,
                guild_id: config.publish.guild_id,
                channel_id: config.publish.channel_id,
                feed_type: config.publish.feed_type,
                limit: 1,
                title_template: config.publish.title_template,
                content_template: config.publish.content_template,
                strip_tags_mentions: config.publish.strip_tags_mentions,
                title_exclusions: config.publish.title_exclusions,
                translate_title_zh_cn: config.publish.translate_title_zh_cn,
                delete_after_publish: config.publish.delete_after_publish
            )
            let snapshotURL = try writeScheduledPublishSnapshot(task, directory: directory, retryVideoPath: expanded)
            let token = tokenForAccount(task.account_id)
            guard !token.isEmpty else {
                reportIssue("请先选择一个已验证的频道账号")
                return
            }
            let process = makeProcess(
                arguments: ["app-publish", "--app-config", snapshotURL.path],
                extraEnvironment: try credentialEnvironment(for: task.account_id)
            )
            publishProcesses[retryID] = process
            publishProcessOutputs[retryID] = ""
            appendLog("重新发布失败视频: \(expanded)")
            streamScheduledPublish(process, taskID: retryID, snapshotURL: snapshotURL)
            try process.run()
            reportInfo("已开始重新发布")
        } catch {
            publishProcesses.removeValue(forKey: retryID)
            publishProcessOutputs.removeValue(forKey: retryID)
            reportIssue("重新发布启动失败：\(error.localizedDescription)")
        }
    }

    func retryFailedPublishes(_ entries: [PublishHistoryEntry]) {
        let candidates = entries.filter { canRetryPublish($0) && !isRetryPublishRunning($0) }
        guard !candidates.isEmpty else {
            reportIssue("没有可重新发布的失败视频")
            return
        }
        for entry in candidates {
            retryPublish(entry)
        }
        reportInfo("已开始重新发布 \(candidates.count) 条失败视频")
    }

    func canRetryPublish(_ entry: PublishHistoryEntry) -> Bool {
        guard !entry.isPublishSuccess else { return false }
        let path = (entry.output_path as NSString).expandingTildeInPath
        return !path.isEmpty && FileManager.default.isReadableFile(atPath: path)
    }

    func isRetryPublishRunning(_ entry: PublishHistoryEntry) -> Bool {
        publishProcesses["retry-\(entry.id.stableIDComponent)"]?.isRunning == true
    }

    func startSchedulerMonitor() {
        guard schedulerTimer == nil else { return }
        schedulerRunning = true
        status = "定时任务自动监控中"
        runScheduledTasksIfNeeded()
        schedulerTimer = Timer.scheduledTimer(withTimeInterval: 60, repeats: true) { [weak self] _ in
            self?.runScheduledTasksIfNeeded()
        }
    }

    private func runScheduledTasksIfNeeded(forceTaskID: String? = nil) {
        let now = Date()
        schedulerNow = now
        for task in config.automation.download_tasks where
            task.enabled
                && isInsideActiveWindow(start: task.active_start, end: task.active_end)
                && (forceTaskID == task.id || isDue(lastScheduledRuns[task.id], minutes: task.interval_minutes)) {
            guard let profile = config.download.profiles.first(where: { $0.id == task.profile_id }),
                  !isProfileDownloading(profile.id) else { continue }
            appendLog("执行定时下载: \(profile.name)")
            if runProfileDownload(profile, scheduleTaskID: task.id) {
                lastScheduledRuns[task.id] = now
            }
        }
        for task in config.automation.publish_tasks where
            task.enabled
                && publishProcesses[task.id]?.isRunning != true
                && isInsideActiveWindow(start: task.active_start, end: task.active_end)
                && (forceTaskID == task.id || isDue(lastScheduledRuns[task.id], minutes: task.interval_minutes)) {
            guard let directory = nextScheduledPublishDirectory(for: task) else { continue }
            lastScheduledRuns[task.id] = now
            appendLog("执行定时发布: \(directory)")
            runScheduledPublish(task, directory: directory)
        }
    }

    private func isDue(_ lastRun: Date?, minutes: Int) -> Bool {
        guard let lastRun else { return true }
        return Date().timeIntervalSince(lastRun) >= Double(max(1, minutes) * 60)
    }

    private func isInsideActiveWindow(start: String, end: String) -> Bool {
        let formatter = DateFormatter()
        formatter.dateFormat = "HH:mm"
        let now = formatter.string(from: Date())
        let normalizedStart = normalizedWallTime(start, fallback: "")
        let normalizedEnd = normalizedWallTime(end, fallback: "")
        guard !normalizedStart.isEmpty, !normalizedEnd.isEmpty else { return false }
        return normalizedStart <= normalizedEnd
            ? (now >= normalizedStart && now <= normalizedEnd)
            : (now >= normalizedStart || now <= normalizedEnd)
    }

    private func normalizedWallTime(_ value: String, fallback: String) -> String {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        let parts = trimmed.split(separator: ":")
        guard parts.count == 2,
              let hour = Int(parts[0]), (0...23).contains(hour),
              let minute = Int(parts[1]), (0...59).contains(minute) else {
            return fallback
        }
        return String(format: "%02d:%02d", hour, minute)
    }

    private func nextScheduledPublishDirectory(for task: ScheduledPublishTask) -> String? {
        let directories = task.directories
        guard !directories.isEmpty else { return nil }
        if task.order == "random" {
            return directories.randomElement()
        }
        let index = nextPublishDirectoryIndexes[task.id, default: 0]
        let directory = directories[index % directories.count]
        nextPublishDirectoryIndexes[task.id] = index + 1
        return directory
    }

    var hasRunnableAutomation: Bool {
        let downloadReady = config.automation.download_tasks.contains { task in
            task.enabled && config.download.profiles.contains { $0.id == task.profile_id }
        }
        let publishReady = config.automation.publish_tasks.contains { $0.enabled && !$0.directories.isEmpty }
        return downloadReady || publishReady
    }

    func isProfileDownloading(_ profileID: String) -> Bool {
        profileDownloadProcesses[profileID]?.isRunning == true
    }

    func scheduledDownloadStatus(for task: ScheduledDownloadTask) -> String {
        if !task.enabled { return "已停止" }
        if !isInsideActiveWindow(start: task.active_start, end: task.active_end) { return "未到运行时间" }
        if isProfileDownloading(task.profile_id) { return "下载中" }
        return lastScheduledRuns[task.id] == nil ? "等待首次执行" : "等待下次执行"
    }

    func scheduledPublishStatus(for task: ScheduledPublishTask) -> String {
        if !task.enabled { return "已停止" }
        if !isInsideActiveWindow(start: task.active_start, end: task.active_end) { return "未到运行时间" }
        if publishProcesses[task.id]?.isRunning == true { return "发布中" }
        return lastScheduledRuns[task.id] == nil ? "等待首次执行" : "等待下次执行"
    }

    func scheduledPublishNextRunText(for task: ScheduledPublishTask) -> String {
        guard task.enabled else { return "下次发布时间：任务已停止" }
        if publishProcesses[task.id]?.isRunning == true {
            return "下次发布时间：本次发布完成后计算"
        }
        let due = lastScheduledRuns[task.id].map {
            $0.addingTimeInterval(Double(max(1, task.interval_minutes) * 60))
        } ?? schedulerNow
        guard let next = nextDateInsideActiveWindow(
            notBefore: max(due, schedulerNow),
            start: task.active_start,
            end: task.active_end
        ) else {
            return "下次发布时间：请检查运行时段"
        }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "zh_CN")
        formatter.timeZone = .current
        formatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        return "下次发布时间：\(formatter.string(from: next))"
    }

    private func nextDateInsideActiveWindow(notBefore: Date, start: String, end: String) -> Date? {
        let normalizedStart = normalizedWallTime(start, fallback: "")
        let normalizedEnd = normalizedWallTime(end, fallback: "")
        guard !normalizedStart.isEmpty, !normalizedEnd.isEmpty else { return nil }
        let startParts = normalizedStart.split(separator: ":").compactMap { Int($0) }
        let endParts = normalizedEnd.split(separator: ":").compactMap { Int($0) }
        guard startParts.count == 2, endParts.count == 2 else { return nil }
        let calendar = Calendar.current
        let today = calendar.startOfDay(for: notBefore)
        for offset in -1...7 {
            guard let day = calendar.date(byAdding: .day, value: offset, to: today),
                  let windowStart = calendar.date(bySettingHour: startParts[0], minute: startParts[1], second: 0, of: day) else {
                continue
            }
            var endDay = day
            if normalizedStart > normalizedEnd {
                endDay = calendar.date(byAdding: .day, value: 1, to: day) ?? day
            }
            guard let windowEnd = calendar.date(bySettingHour: endParts[0], minute: endParts[1], second: 59, of: endDay) else {
                continue
            }
            let candidate = max(notBefore, windowStart)
            if candidate <= windowEnd {
                return candidate
            }
        }
        return nil
    }

    @discardableResult
    private func runProcess(arguments: [String], extraEnvironment: [String: String] = [:]) -> Bool {
        guard !busy else {
            appendLog("已有任务在运行")
            reportIssue("已有单视频任务或配置检查正在运行")
            return false
        }
        busy = true
        genericProcessOutput = ""
        let process = makeProcess(arguments: arguments, extraEnvironment: extraEnvironment)
        activeGenericProcess = process
        stream(process)
        do {
            try process.run()
            return true
        } catch {
            busy = false
            activeGenericProcess = nil
            appendLog("命令启动失败: \(error.localizedDescription)")
            reportIssue("任务启动失败：\(error.localizedDescription)")
            return false
        }
    }

    private func runTencentStatus(arguments: [String], extraEnvironment: [String: String] = [:]) {
        guard !busy else {
            appendLog("已有任务在运行")
            return
        }
        busy = true
        tencentStatusText = "正在验证"
        tencentStatusOK = false
        let tokenWasProvided = !(extraEnvironment["QQ_AI_CONNECT_TOKEN_INPUT"] ?? "").isEmpty
        DispatchQueue.global(qos: .userInitiated).async {
            do {
                if let token = extraEnvironment["QQ_AI_CONNECT_TOKEN_INPUT"], !token.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                    try self.writeTencentToken(token)
                }
                let statusOutput = try self.runTencentCLI(["login", "status", "--json"])
                let status = try JSONDecoder().decode(TencentCLIStatus.self, from: Data(statusOutput.utf8))
                let loggedIn = status.success && (status.data.valid == true || status.data.isLoggedIn == true)
                var response = TencentStatusResponse(
                    ok: loggedIn,
                    logged_in: loggedIn,
                    token_source: status.data.tokenSource ?? "",
                    nickname: "",
                    global_nickname: "",
                    is_guild_author: false,
                    error: loggedIn ? "" : "腾讯频道 Token 未配置或未通过登录检查"
                )
                if loggedIn {
                    let userOutput = try self.runTencentCLI(["manage", "get-user-info", "--json"])
                    let user = try JSONDecoder().decode(TencentCLIUser.self, from: Data(userOutput.utf8))
                    if user.success {
                        response.nickname = user.data.nickname ?? ""
                        response.global_nickname = user.data.global_nickname ?? ""
                        response.is_guild_author = user.data.is_guild_author ?? false
                    }
                }
                DispatchQueue.main.async {
                    self.busy = false
                    if tokenWasProvided {
                        self.tencentTokenInput = ""
                    }
                    self.handleTencentStatusResponse(response)
                }
            } catch {
                DispatchQueue.main.async {
                    self.busy = false
                    if tokenWasProvided {
                        self.tencentTokenInput = ""
                    }
                    self.tencentStatusOK = false
                    self.tencentStatusText = "验证失败"
                    self.appendLog("腾讯频道检查失败: \(error.localizedDescription)")
                    if !self.suppressNextTencentFailureNotice {
                        self.reportIssue("腾讯频道验证失败：\(error.localizedDescription)")
                    }
                    self.suppressNextTencentFailureNotice = false
                }
            }
        }
    }

    private func handleTencentStatusResponse(_ response: TencentStatusResponse) {
        tencentStatusOK = response.ok && response.logged_in
        if tencentStatusOK {
            let name = response.nickname.isEmpty ? (response.global_nickname.isEmpty ? "当前账号" : response.global_nickname) : response.nickname
            let author = response.is_guild_author ? "创作者" : "非创作者"
            let source = response.token_source.isEmpty ? "未知来源" : response.token_source
            tencentStatusText = "\(name) · \(author)"
            tencentNickname = name
            if let index = config.tencent_accounts.firstIndex(where: { $0.id == config.publish.account_id }) {
                config.tencent_accounts[index].nickname = name
                config.tencent_accounts[index].is_guild_author = response.is_guild_author
                config.tencent_accounts[index].verified = true
                save()
            }
            reportInfo("腾讯频道验证成功，\(greetingText)")
            appendLog("腾讯频道验证成功: \(name), \(author), 来源 \(source)")
        } else {
            tencentNickname = ""
            tencentStatusText = response.error.isEmpty ? "验证失败" : response.error
            appendLog("腾讯频道验证失败: \(tencentStatusText)")
            if !suppressNextTencentFailureNotice {
                reportIssue("腾讯频道验证失败：\(tencentStatusText)")
            }
        }
        suppressNextTencentFailureNotice = false
    }

    private func runTencentCLI(_ arguments: [String], token: String = "") throws -> String {
        let bundledBin = Bundle.main.resourceURL?
            .appendingPathComponent("runtime/bin")
            .path ?? ""
        let cliCandidates = [
            "\(bundledBin)/tencent-channel-cli",
            "/opt/homebrew/bin/tencent-channel-cli",
            "/usr/local/bin/tencent-channel-cli",
            "\(NSHomeDirectory())/.local/bin/tencent-channel-cli"
        ]
        guard let cli = cliCandidates.first(where: { FileManager.default.isExecutableFile(atPath: $0) }) else {
            throw NSError(domain: "VideocpStudio", code: 1, userInfo: [NSLocalizedDescriptionKey: "未找到 tencent-channel-cli"])
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: cli)
        process.currentDirectoryURL = URL(fileURLWithPath: NSHomeDirectory())
        process.arguments = arguments
        var environment = ProcessInfo.processInfo.environment
        environment["PATH"] = "\(bundledBin):/opt/homebrew/bin:/usr/local/bin:" + (environment["PATH"] ?? "")
        environment["VIDEOCP_BUNDLED_BIN"] = bundledBin
        var temporaryCredentialURL: URL?
        if !token.isEmpty {
            let url = FileManager.default.temporaryDirectory
                .appendingPathComponent("videocp-account-\(UUID().uuidString).env")
            try "QQ_AI_CONNECT_TOKEN=\(token)\n".write(to: url, atomically: true, encoding: .utf8)
            try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: url.path)
            environment["QQ_AI_CONNECT_DOTENV"] = url.path
            temporaryCredentialURL = url
        }
        process.environment = environment
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        try process.run()
        process.waitUntilExit()
        if let temporaryCredentialURL {
            try? FileManager.default.removeItem(at: temporaryCredentialURL)
        }
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        let output = String(data: data, encoding: .utf8) ?? ""
        guard process.terminationStatus == 0 else {
            throw NSError(domain: "VideocpStudio", code: Int(process.terminationStatus), userInfo: [NSLocalizedDescriptionKey: output.trimmingCharacters(in: .whitespacesAndNewlines)])
        }
        return output
    }

    private func writeTencentToken(_ token: String) throws {
        let envURL = URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent(".qqcli/.env")
        try FileManager.default.createDirectory(at: envURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        var lines: [String] = []
        if let existing = try? String(contentsOf: envURL, encoding: .utf8) {
            lines = existing.split(separator: "\n", omittingEmptySubsequences: false)
                .map(String.init)
                .filter { !$0.hasPrefix("QQ_AI_CONNECT_TOKEN=") }
        }
        lines.append("QQ_AI_CONNECT_TOKEN=\(token.trimmingCharacters(in: .whitespacesAndNewlines))")
        try (lines.joined(separator: "\n") + "\n").write(to: envURL, atomically: true, encoding: .utf8)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: envURL.path)
    }

    private func makeProcess(arguments: [String], extraEnvironment: [String: String] = [:]) -> Process {
        let process = Process()
        let runtimeRoot = preferredRuntimeRoot()
        // GUI child processes must avoid enumerating iCloud-backed project folders.
        // The build script mirrors code and dependencies into this local cache.
        let cacheRoot = URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent("Library/Caches/videocp/runtime")
        let bundledRuntime = Bundle.main.resourceURL?.appendingPathComponent("runtime")
        let hasBundledRuntime = bundledRuntime.map {
            FileManager.default.isExecutableFile(atPath: $0.appendingPathComponent("python/bin/python3").path)
        } ?? false
        let runtimeCodeRoot = hasBundledRuntime ? bundledRuntime! : cacheRoot
        let bundledAssetRoot = bundledRuntime.map {
            FileManager.default.fileExists(atPath: $0.appendingPathComponent("bin/ffmpeg").path)
                ? $0
                : runtimeCodeRoot
        } ?? runtimeCodeRoot
        let pythonURL = hasBundledRuntime
            ? runtimeCodeRoot.appendingPathComponent("python/bin/python3")
            : cachedPythonURL(in: cacheRoot)
        let sitePackages = runtimeCodeRoot.appendingPathComponent("site-packages").path
        let bundledBin = bundledAssetRoot.appendingPathComponent("bin").path
        let bundledYouTubeHelper = bundledAssetRoot.appendingPathComponent("bgutil-server").path
        let bundledDenoCache = bundledAssetRoot.appendingPathComponent("bgutil-deno-cache")
        let userDenoCache = URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent("Library/Caches/videocp/bgutil-deno-cache")
        seedBundledDenoCacheIfNeeded(from: bundledDenoCache, to: userDenoCache)
        process.currentDirectoryURL = URL(fileURLWithPath: NSHomeDirectory())
        process.executableURL = URL(fileURLWithPath: "/bin/zsh")
        let pythonPathEntries = [runtimeCodeRoot.path, sitePackages]
            .joined(separator: ":")
            .shellQuoted
        let cliCode = "from videocp.cli import main; raise SystemExit(main())".shellQuoted
        let cliArgs = arguments
            .map { $0 == configURL.path ? runtimeConfigURL.path : $0 }
            .map(\.shellQuoted)
            .joined(separator: " ")
        if let pythonURL {
            process.arguments = ["-lc", "PYTHONPATH=\(pythonPathEntries) exec \(pythonURL.path.shellQuoted) -c \(cliCode) \(cliArgs)"]
        } else {
            process.arguments = ["-lc", "echo 'Videocp Studio 内置 Python 运行时缺失，请重新安装完整 App。' >&2; exit 127"]
        }
        var environment = ProcessInfo.processInfo.environment
        environment.removeValue(forKey: "__PYVENV_LAUNCHER__")
        environment.removeValue(forKey: "PYTHONHOME")
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        environment["PATH"] = "\(bundledBin):/opt/homebrew/bin:/usr/local/bin:\(runtimeRoot.path)/.venv/bin:" + (environment["PATH"] ?? "")
        environment["PYTHONPATH"] = [runtimeCodeRoot.path, sitePackages].joined(separator: ":")
        environment["VIDEOCP_BUNDLED_BIN"] = bundledBin
        environment["VIDEOCP_BUNDLED_BGUTIL_SERVER"] = bundledYouTubeHelper
        environment["DENO_DIR"] = userDenoCache.path
        environment["DENO_NO_PROMPT"] = "1"
        environment["DENO_NO_UPDATE_CHECK"] = "1"
        environment["HOME"] = NSHomeDirectory()
        for (key, value) in extraEnvironment {
            environment[key] = value
        }
        process.environment = environment
        return process
    }

    private func seedBundledDenoCacheIfNeeded(from source: URL, to destination: URL) {
        let fileManager = FileManager.default
        let marker = "npm/registry.npmjs.org/commander/registry.json"
        guard fileManager.fileExists(atPath: source.appendingPathComponent(marker).path),
              !fileManager.fileExists(atPath: destination.appendingPathComponent(marker).path) else {
            return
        }
        do {
            try fileManager.createDirectory(at: destination.deletingLastPathComponent(), withIntermediateDirectories: true)
            if fileManager.fileExists(atPath: destination.path) {
                try fileManager.removeItem(at: destination)
            }
            try fileManager.copyItem(at: source, to: destination)
        } catch {
            appendLog("YouTube 辅助缓存初始化失败，将在首次下载时自动补齐: \(error.localizedDescription)")
        }
    }

    private var runtimeConfigURL: URL {
        URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent("Library/Caches/videocp/runtime/mac-app.json")
    }

    private func mirrorRuntimeConfig(_ data: Data) throws {
        try writeRuntimeConfig(data, to: runtimeConfigURL)
    }

    private func writeProfileDownloadSnapshot(_ profile: DownloadProfile) throws -> URL {
        var snapshot = config
        snapshot.download.inputs_text = profile.url
        snapshot.download.order = profile.order
        snapshot.download.quality = profile.quality
        snapshot.download.count = max(1, profile.count)
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        let data = try encoder.encode(snapshot)
        let url = runtimeConfigURL.deletingLastPathComponent()
            .appendingPathComponent("profile-download-\(profile.id).json")
        try writeRuntimeConfig(data, to: url)
        return url
    }

    private func writeHistoryRedownloadSnapshot(sourceURL: String, quality: String, entryID: String) throws -> URL {
        var snapshot = config
        snapshot.download.inputs_text = sourceURL
        snapshot.download.quality = quality
        snapshot.download.count = 1
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        let data = try encoder.encode(snapshot)
        let safeID = entryID.replacingOccurrences(
            of: "[^A-Za-z0-9._-]",
            with: "-",
            options: .regularExpression
        )
        let url = runtimeConfigURL.deletingLastPathComponent()
            .appendingPathComponent("history-redownload-\(safeID).json")
        try writeRuntimeConfig(data, to: url)
        return url
    }

    private func writeScheduledPublishSnapshot(_ task: ScheduledPublishTask, directory: String, retryVideoPath: String = "") throws -> URL {
        var snapshot = config
        snapshot.publish.input_dir = directory
        snapshot.publish.scope = task.scope
        snapshot.publish.guild_id = task.guild_id
        snapshot.publish.channel_id = task.channel_id
        snapshot.publish.feed_type = task.feed_type
        snapshot.publish.limit = max(1, task.limit)
        snapshot.publish.title_template = task.title_template
        snapshot.publish.content_template = task.content_template
        snapshot.publish.strip_tags_mentions = task.strip_tags_mentions
        snapshot.publish.title_exclusions = task.title_exclusions
        snapshot.publish.translate_title_zh_cn = task.translate_title_zh_cn
        snapshot.publish.delete_after_publish = task.delete_after_publish
        snapshot.publish.retry_video_path = retryVideoPath
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        let data = try encoder.encode(snapshot)
        let url = runtimeConfigURL.deletingLastPathComponent()
            .appendingPathComponent("scheduled-publish-\(task.id).json")
        try writeRuntimeConfig(data, to: url)
        return url
    }

    private func writeRuntimeConfig(_ data: Data, to cacheURL: URL) throws {
        var object = try JSONSerialization.jsonObject(with: data) as? [String: Any] ?? [:]
        let basePath = configURL.deletingLastPathComponent().path
        func absolutePath(_ value: Any?) -> Any? {
            guard let raw = value as? String, !raw.isEmpty, !raw.hasPrefix("~"), !raw.hasPrefix("/") else {
                return value
            }
            return URL(fileURLWithPath: basePath).appendingPathComponent(raw).standardized.path
        }
        object["tasks_file"] = absolutePath(object["tasks_file"])
        if var download = object["download"] as? [String: Any] {
            download["output_dir"] = absolutePath(download["output_dir"])
            download["history_file"] = absolutePath(download["history_file"])
            download["youtube_cookies_path"] = absolutePath(download["youtube_cookies_path"])
            object["download"] = download
        }
        if var publish = object["publish"] as? [String: Any] {
            publish["input_dir"] = absolutePath(publish["input_dir"])
            publish["history_file"] = absolutePath(publish["history_file"])
            object["publish"] = publish
        }
        if var sync = object["sync"] as? [String: Any] {
            sync["history_file"] = absolutePath(sync["history_file"])
            object["sync"] = sync
        }
        try FileManager.default.createDirectory(at: cacheURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        let cacheData = try JSONSerialization.data(withJSONObject: object, options: [.prettyPrinted, .sortedKeys])
        try cacheData.write(to: cacheURL, options: .atomic)
        try FileManager.default.setAttributes([.posixPermissions: 0o600], ofItemAtPath: cacheURL.path)
    }

    private func cachedPythonURL(in cacheRoot: URL) -> URL? {
        let fileManager = FileManager.default
        let pathFile = cacheRoot.appendingPathComponent("python-path")
        if let path = try? String(contentsOf: pathFile, encoding: .utf8)
            .trimmingCharacters(in: .whitespacesAndNewlines),
           !path.isEmpty,
           fileManager.isExecutableFile(atPath: path) {
            return URL(fileURLWithPath: path)
        }
        let sourcePython = preferredRuntimeRoot()
            .appendingPathComponent(".venv/bin/python3")
            .resolvingSymlinksInPath()
        return fileManager.isExecutableFile(atPath: sourcePython.path) ? sourcePython : nil
    }

    private func preferredRuntimeRoot() -> URL {
        let canonicalRoot = appRoot.resolvingSymlinksInPath().path
        let documentsRoot = URL(fileURLWithPath: NSHomeDirectory())
            .appendingPathComponent("Documents/发帖项目/videocp")
        if FileManager.default.fileExists(atPath: documentsRoot.path),
           documentsRoot.resolvingSymlinksInPath().path == canonicalRoot {
            return documentsRoot
        }
        return appRoot
    }

    private func stream(_ process: Process) {
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            DispatchQueue.main.async {
                guard let self else { return }
                self.genericProcessOutput += text
                self.appendLog(text.trimmingCharacters(in: .newlines))
            }
        }
        process.terminationHandler = { [weak self] proc in
            DispatchQueue.main.async {
                self?.appendLog("命令结束，退出码 \(proc.terminationStatus)")
                if proc === self?.schedulerProcess {
                    self?.schedulerRunning = false
                    self?.schedulerProcess = nil
                    self?.status = "定时器已退出"
                } else {
                    self?.busy = false
                    self?.activeGenericProcess = nil
                    if proc.terminationStatus != 0 {
                        self?.reportIssue(self?.friendlyFailure(from: self?.genericProcessOutput ?? "") ?? "任务执行失败")
                    }
                    self?.genericProcessOutput = ""
                    self?.loadPublishHistory()
                }
            }
        }
    }

    private func streamScheduledPublish(_ process: Process, taskID: String, snapshotURL: URL) {
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            DispatchQueue.main.async {
                self?.publishProcessOutputs[taskID, default: ""] += text
                self?.appendLog(text.trimmingCharacters(in: .newlines))
            }
        }
        process.terminationHandler = { [weak self] proc in
            DispatchQueue.main.async {
                guard let self else { return }
                try? FileManager.default.removeItem(at: snapshotURL)
                let output = self.publishProcessOutputs.removeValue(forKey: taskID) ?? ""
                self.publishProcesses.removeValue(forKey: taskID)
                self.appendLog("定时发布结束，退出码 \(proc.terminationStatus)")
                if proc.terminationStatus != 0 {
                    self.reportIssue("定时发布失败：\(self.friendlyFailure(from: output))")
                }
                self.loadPublishHistory()
            }
        }
    }

    private func streamProfileDownload(_ process: Process, profileID: String, snapshotURL: URL) {
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            DispatchQueue.main.async {
                self?.profileProcessOutputs[profileID, default: ""] += text
                self?.updateDownloadProgress(from: text, profileID: profileID)
                self?.appendLog(text.trimmingCharacters(in: .newlines))
            }
        }
        process.terminationHandler = { [weak self] proc in
            DispatchQueue.main.async {
                guard let self else { return }
                try? FileManager.default.removeItem(at: snapshotURL)
                let wasStopping = self.profileProgress[profileID]?.status == "正在停止"
                let output = self.profileProcessOutputs.removeValue(forKey: profileID) ?? ""
                self.profileDownloadProcesses.removeValue(forKey: profileID)
                self.scheduledDownloadTaskIDsByProfile.removeValue(forKey: profileID)
                self.appendLog("主页下载结束，退出码 \(proc.terminationStatus)")
                self.finishActiveDownload(profileID: profileID, exitCode: proc.terminationStatus)
                if proc.terminationStatus != 0 {
                    if wasStopping {
                        self.profileProgress[profileID]?.status = "已停止"
                        self.reportInfo("主页下载已停止")
                    } else {
                        self.reportIssue(self.friendlyFailure(from: output))
                    }
                }
            }
        }
    }

    private func streamSingleDownload(_ process: Process) {
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
            DispatchQueue.main.async {
                self?.singleProcessOutput += text
                self?.updateSingleDownloadProgress(from: text)
                self?.appendLog(text.trimmingCharacters(in: .newlines))
            }
        }
        process.terminationHandler = { [weak self] proc in
            DispatchQueue.main.async {
                guard let self else { return }
                self.appendLog("命令结束，退出码 \(proc.terminationStatus)")
                self.busy = false
                if proc.terminationStatus != 0 {
                    let reason = self.friendlyFailure(from: self.singleProcessOutput)
                    self.singleDownloadProgress = SingleDownloadProgress(phase: .failed, message: reason)
                    self.reportIssue(reason)
                } else if self.singleDownloadProgress.phase == .downloading {
                    self.singleDownloadProgress = SingleDownloadProgress(phase: .success, message: "下载成功")
                }
                self.singleProcessOutput = ""
            }
        }
    }

    func appendLog(_ line: String) {
        guard !line.isEmpty else { return }
        let newLines = line
            .split(separator: "\n", omittingEmptySubsequences: false)
            .map { String($0).trimmingCharacters(in: .newlines) }
            .filter { !$0.isEmpty }
            .map { value in
                value.count > maxVisibleLogLineLength
                    ? String(value.prefix(maxVisibleLogLineLength)) + " ..."
                    : value
            }
        guard !newLines.isEmpty else { return }
        appendFullLogLines(newLines)
        logLines.append(contentsOf: newLines)
        if logLines.count > maxVisibleLogLines {
            let overflow = logLines.count - maxVisibleLogLines
            droppedLogLineCount += overflow
            logLines.removeFirst(overflow)
        }
        logLineCount = logLines.count
        logs = logLines.joined(separator: "\n")
    }

    private func appendFullLogLines(_ lines: [String]) {
        let formatter = ISO8601DateFormatter()
        let text = lines.map { "[\(formatter.string(from: Date()))] \($0)" }.joined(separator: "\n") + "\n"
        guard let data = text.data(using: .utf8) else { return }
        if FileManager.default.fileExists(atPath: logFileURL.path),
           let handle = try? FileHandle(forWritingTo: logFileURL) {
            defer { try? handle.close() }
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: data)
        } else {
            try? data.write(to: logFileURL, options: .atomic)
        }
    }

    func clearLogs() {
        logLines.removeAll()
        logs = ""
        logLineCount = 0
        droppedLogLineCount = 0
    }

    func openLogDirectory() {
        try? FileManager.default.createDirectory(at: logDirectoryURL, withIntermediateDirectories: true)
        NSWorkspace.shared.open(logDirectoryURL)
    }

    private func friendlyFailure(from output: String) -> String {
        let lines = output.split(separator: "\n").map(String.init)
        if let error = lines.last(where: { $0.localizedCaseInsensitiveContains("error") || $0.contains("失败") }) {
            return String(error.prefix(260))
        }
        return "任务执行失败，请检查配置后重试"
    }

    func loadPublishHistory() {
        let path = resolvedSupportPath(config.publish.history_file)
        guard let data = try? Data(contentsOf: path),
              let file = try? JSONDecoder().decode(PublishHistoryFile.self, from: data) else {
            publishHistory = []
            return
        }
        publishHistory = file.entries.sorted { $0.synced_at > $1.synced_at }
    }

    private func resolvedSupportPath(_ value: String) -> URL {
        let expanded = (value as NSString).expandingTildeInPath
        if expanded.hasPrefix("/") { return URL(fileURLWithPath: expanded) }
        return configURL.deletingLastPathComponent().appendingPathComponent(expanded)
    }

    private func validateBundledRuntime() {
        let bundledRuntime = Bundle.main.resourceURL?.appendingPathComponent("runtime")
        let bundledPython = bundledRuntime?.appendingPathComponent("python/bin/python3")
        let hasBundledRuntime = bundledPython.map {
            FileManager.default.isExecutableFile(atPath: $0.path)
        } ?? false
        let codeRuntime = hasBundledRuntime
            ? bundledRuntime!
            : URL(fileURLWithPath: NSHomeDirectory()).appendingPathComponent("Library/Caches/videocp/runtime")
        let bundledAssets = [
            "bin/ffmpeg",
            "bin/ffprobe",
            "bin/deno",
            "bin/tencent-channel-cli",
            "bgutil-server/src/generate_once.ts",
            "bgutil-server/node_modules/commander/package.json",
        ]
        let codeAssets = [
            "site-packages/yt_dlp/__init__.py",
            "site-packages/playwright/__init__.py",
        ]
        let missingBundled = bundledAssets.filter {
            guard let bundledRuntime else { return true }
            return !FileManager.default.fileExists(atPath: bundledRuntime.appendingPathComponent($0).path)
        }
        let missingCode = codeAssets.filter {
            !FileManager.default.fileExists(atPath: codeRuntime.appendingPathComponent($0).path)
        }
        let pythonMissing = hasBundledRuntime
            ? false
            : cachedPythonURL(in: codeRuntime) == nil
        let allMissing = (pythonMissing ? ["python/bin/python3"] : []) + missingBundled + missingCode
        if !allMissing.isEmpty {
            reportIssue("App 安装不完整，请重新安装。缺少：\(allMissing.joined(separator: "、"))")
        }
    }

    var greetingText: String {
        guard tencentStatusOK else { return "" }
        let hour = Calendar.current.component(.hour, from: Date())
        let period = hour < 12 ? "上午好" : (hour < 18 ? "下午好" : "晚上好")
        return "\(period)，\(tencentNickname.isEmpty ? "创作者" : tencentNickname)"
    }

    func platformName(for url: String) -> String {
        let lower = url.lowercased()
        if lower.contains("youtube.com") || lower.contains("youtu.be") { return "YouTube" }
        if lower.contains("douyin.com") { return "抖音" }
        if lower.contains("xiaohongshu.com") || lower.contains("xhslink.com") { return "小红书" }
        if lower.contains("bilibili.com") || lower.contains("b23.tv") { return "哔哩哔哩" }
        if lower.contains("instagram.com") { return "Instagram" }
        return "其他"
    }

    func supportsQualitySelection(for url: String) -> Bool {
        let platform = platformName(for: url)
        return platform != "抖音" && platform != "小红书"
    }

    func localVideoCount(for profile: DownloadProfile) -> Int {
        struct LocalVideo {
            let contentID: String
            let site: String
            let author: String
            let parentName: String
        }

        var rootPaths: Set<String> = []
        let configuredPaths = [config.download.output_dir, config.publish.input_dir]
            + config.automation.publish_tasks.flatMap(\.directories)
        for path in configuredPaths {
            let trimmed = path.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !trimmed.isEmpty else { continue }
            let resolved = resolvedSupportPath(trimmed).standardizedFileURL.path
            if FileManager.default.fileExists(atPath: resolved) {
                rootPaths.insert(resolved)
            }
        }
        let appDefaultDownloads = configURL.deletingLastPathComponent()
            .appendingPathComponent("downloads")
            .standardizedFileURL
        if FileManager.default.fileExists(atPath: appDefaultDownloads.path) {
            rootPaths.insert(appDefaultDownloads.path)
        }
        for entry in downloadHistoryEntries() {
            let outputPath = entry.output_path.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !outputPath.isEmpty else { continue }
            let directory = URL(fileURLWithPath: (outputPath as NSString).expandingTildeInPath)
                .deletingLastPathComponent()
                .standardizedFileURL
            if FileManager.default.fileExists(atPath: directory.path) {
                rootPaths.insert(directory.path)
            }
        }
        guard !rootPaths.isEmpty else { return 0 }

        let videoExtensions = Set(["mp4", "m4v", "mov", "webm", "mkv"])
        var videos: [LocalVideo] = []
        var seenSidecars: Set<String> = []
        var seenContentKeys: Set<String> = []
        for rootPath in rootPaths {
            let root = URL(fileURLWithPath: rootPath)
            guard let enumerator = FileManager.default.enumerator(
                at: root,
                includingPropertiesForKeys: [.isRegularFileKey],
                options: [.skipsHiddenFiles]
            ) else { continue }
            for case let sidecar as URL in enumerator where sidecar.pathExtension.lowercased() == "json" {
                guard seenSidecars.insert(sidecar.standardizedFileURL.path).inserted,
                      let data = try? Data(contentsOf: sidecar),
                      let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                    continue
                }
                let outputPath = (object["output_path"] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
                let siblingMediaURL = videoExtensions
                    .map { sidecar.deletingPathExtension().appendingPathExtension($0) }
                    .first { FileManager.default.fileExists(atPath: $0.path) }
                let declaredMediaURL = outputPath.isEmpty
                    ? nil
                    : URL(fileURLWithPath: (outputPath as NSString).expandingTildeInPath)
                guard let mediaURL = siblingMediaURL ?? declaredMediaURL,
                      videoExtensions.contains(mediaURL.pathExtension.lowercased()),
                      FileManager.default.fileExists(atPath: mediaURL.path) else {
                    continue
                }
                let contentID = String(describing: object["content_id"] ?? "")
                let site = String(describing: object["site"] ?? "").lowercased()
                let contentKey = contentID.isEmpty ? mediaURL.standardizedFileURL.path : "\(site):\(contentID)"
                guard seenContentKeys.insert(contentKey).inserted else { continue }
                videos.append(
                    LocalVideo(
                        contentID: contentID,
                        site: site,
                        author: normalizeProfileName(String(describing: object["author"] ?? "")),
                        parentName: normalizeProfileName(mediaURL.deletingLastPathComponent().lastPathComponent)
                    )
                )
            }
        }

        let expectedSite = platformKey(for: profile.url)
        let firstVideoID = contentID(from: profile.first_video_url)
        var authorAliases = Set([normalizeProfileName(profile.name)].filter { !$0.isEmpty })
        if !firstVideoID.isEmpty {
            for video in videos where video.contentID == firstVideoID && !video.author.isEmpty {
                authorAliases.insert(video.author)
            }
            if let historyAuthor = downloadHistoryAuthor(for: firstVideoID), !historyAuthor.isEmpty {
                authorAliases.insert(historyAuthor)
            }
        }
        let decodedProfileURL = profile.url.removingPercentEncoding ?? profile.url
        let handle = decodedProfileURL
            .split(separator: "/")
            .first(where: { $0.hasPrefix("@") })
            .map { normalizeProfileName(String($0)) } ?? ""
        if !handle.isEmpty {
            authorAliases.insert(handle)
        }

        return videos.filter { video in
            let siteMatches = expectedSite.isEmpty || video.site.isEmpty || video.site == expectedSite
            guard siteMatches else { return false }
            return authorAliases.isEmpty || authorAliases.contains { alias in
                (!video.author.isEmpty && (video.author.contains(alias) || alias.contains(video.author)))
                    || video.parentName.contains(alias)
                    || alias.contains(video.parentName)
            }
        }.count
    }

    func downloadHistory(for profile: DownloadProfile) -> [DownloadHistoryEntry] {
        let expectedSite = platformKey(for: profile.url)
        let aliases = profileAuthorAliases(for: profile)
        return downloadHistoryEntries()
            .filter { entry in
                guard entry.task_name == "directory_download",
                      entry.status == "ok",
                      expectedSite.isEmpty || entry.site.lowercased() == expectedSite else {
                    return false
                }
                let author = normalizeProfileName(entry.author)
                let parent = normalizeProfileName(
                    URL(fileURLWithPath: entry.output_path).deletingLastPathComponent().lastPathComponent
                )
                return aliases.isEmpty || aliases.contains { alias in
                    (!author.isEmpty && (author.contains(alias) || alias.contains(author)))
                        || parent.contains(alias)
                        || alias.contains(parent)
                }
            }
            .sorted { $0.synced_at > $1.synced_at }
    }

    func openProfileDownloadDirectory(_ profile: DownloadProfile) {
        let entries = downloadHistory(for: profile)
        var directoryCounts: [String: Int] = [:]
        for entry in entries {
            let path = (entry.output_path as NSString).expandingTildeInPath
            let directory = URL(fileURLWithPath: path).deletingLastPathComponent().standardizedFileURL.path
            if FileManager.default.fileExists(atPath: directory) {
                directoryCounts[directory, default: 0] += 1
            }
        }
        let aliases = profileAuthorAliases(for: profile)
        let expectedSite = platformKey(for: profile.url)
        let fallbackRoots = [
            resolvedSupportPath(config.download.output_dir),
            configURL.deletingLastPathComponent().appendingPathComponent("downloads")
        ]
        for root in fallbackRoots where FileManager.default.fileExists(atPath: root.path) {
            guard let children = try? FileManager.default.contentsOfDirectory(
                at: root,
                includingPropertiesForKeys: [.isDirectoryKey],
                options: [.skipsHiddenFiles]
            ) else { continue }
            for directory in children {
                let name = normalizeProfileName(directory.lastPathComponent)
                let siteMatches = expectedSite.isEmpty || name.contains(expectedSite)
                let authorMatches = aliases.contains { name.contains($0) || $0.contains(name) }
                if siteMatches && authorMatches {
                    directoryCounts[directory.standardizedFileURL.path, default: 0] += 1
                }
            }
        }
        guard let bestPath = directoryCounts.max(by: { $0.value < $1.value })?.key else {
            reportIssue("没有找到这个 UP 主的本地下载目录")
            return
        }
        NSWorkspace.shared.open(URL(fileURLWithPath: bestPath))
    }

    func downloadHistoryFileExists(_ entry: DownloadHistoryEntry) -> Bool {
        let path = (entry.output_path as NSString).expandingTildeInPath
        return !path.isEmpty && FileManager.default.fileExists(atPath: path)
    }

    func revealDownloadHistoryFile(_ entry: DownloadHistoryEntry) {
        let path = (entry.output_path as NSString).expandingTildeInPath
        guard FileManager.default.fileExists(atPath: path) else {
            reportIssue("这个视频文件已经不在本地，但去重记录仍然保留")
            return
        }
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: path)])
    }

    func isHistoryRedownloading(_ entry: DownloadHistoryEntry) -> Bool {
        historyRedownloadProcesses[entry.id]?.isRunning == true
    }

    var hasActiveHistoryRedownload: Bool {
        historyRedownloadProcesses.values.contains { $0.isRunning }
    }

    func redownloadHistoryEntry(_ entry: DownloadHistoryEntry, profile: DownloadProfile) {
        guard requireDownloadDirectory() else { return }
        guard !isHistoryRedownloading(entry) else { return }
        guard !hasActiveHistoryRedownload else {
            reportIssue("已有视频正在重新下载，请等当前任务完成后再点下一条")
            return
        }
        guard let sourceURL = downloadSourceURL(for: entry) else {
            historyRedownloadStatus[entry.id] = "缺少原视频链接"
            reportIssue("无法还原这条记录的原视频链接")
            return
        }
        do {
            let snapshotURL = try writeHistoryRedownloadSnapshot(
                sourceURL: sourceURL,
                quality: profile.quality,
                entryID: entry.id
            )
            let process = makeProcess(
                arguments: ["app-download", "--app-config", snapshotURL.path, "--force-redownload"]
            )
            let pipe = Pipe()
            process.standardOutput = pipe
            process.standardError = pipe
            historyRedownloadStatus[entry.id] = "正在重新下载"
            historyRedownloadOutputs[entry.id] = ""
            historyRedownloadProcesses[entry.id] = process
            pipe.fileHandleForReading.readabilityHandler = { [weak self] handle in
                let data = handle.availableData
                guard !data.isEmpty, let text = String(data: data, encoding: .utf8) else { return }
                DispatchQueue.main.async {
                    self?.historyRedownloadOutputs[entry.id, default: ""] += text
                    self?.appendLog(text.trimmingCharacters(in: .newlines))
                }
            }
            process.terminationHandler = { [weak self] proc in
                DispatchQueue.main.async {
                    guard let self else { return }
                    pipe.fileHandleForReading.readabilityHandler = nil
                    try? FileManager.default.removeItem(at: snapshotURL)
                    let output = self.historyRedownloadOutputs.removeValue(forKey: entry.id) ?? ""
                    self.historyRedownloadProcesses.removeValue(forKey: entry.id)
                    if proc.terminationStatus == 0 {
                        self.historyRedownloadStatus[entry.id] = "重新下载成功"
                        let qualityText = profile.quality == "best" ? "最高画质" : "\(profile.quality)p"
                        self.reportInfo("视频已按 \(qualityText) 重新下载")
                    } else {
                        let reason = self.friendlyFailure(from: output)
                        self.historyRedownloadStatus[entry.id] = "失败：\(reason)"
                        self.reportIssue(reason)
                    }
                }
            }
            try process.run()
        } catch {
            historyRedownloadProcesses.removeValue(forKey: entry.id)
            historyRedownloadOutputs.removeValue(forKey: entry.id)
            historyRedownloadStatus[entry.id] = "启动失败"
            reportIssue("重新下载启动失败：\(error.localizedDescription)")
        }
    }

    private func downloadSourceURL(for entry: DownloadHistoryEntry) -> String? {
        let outputPath = (entry.output_path as NSString).expandingTildeInPath
        if !outputPath.isEmpty {
            let sidecarURL = URL(fileURLWithPath: outputPath)
                .deletingPathExtension()
                .appendingPathExtension("json")
            if let data = try? Data(contentsOf: sidecarURL),
               let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                for key in ["canonical_url", "source_url", "page_url"] {
                    if let value = object[key] as? String, !value.isEmpty {
                        return value
                    }
                }
            }
        }
        let contentID = entry.content_id.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !contentID.isEmpty else { return nil }
        switch entry.site.lowercased() {
        case "youtube":
            return "https://www.youtube.com/watch?v=\(contentID)"
        case "bilibili":
            return "https://www.bilibili.com/video/\(contentID)"
        case "douyin":
            return "https://www.douyin.com/video/\(contentID)"
        case "xiaohongshu":
            return "https://www.xiaohongshu.com/explore/\(contentID)"
        case "instagram":
            return "https://www.instagram.com/reel/\(contentID)/"
        default:
            return nil
        }
    }

    private func downloadHistoryEntries() -> [DownloadHistoryEntry] {
        let historyURL = resolvedSupportPath(config.download.history_file)
        guard let data = try? Data(contentsOf: historyURL),
              let file = try? JSONDecoder().decode(DownloadHistoryFile.self, from: data) else {
            return []
        }
        return file.entries
    }

    private func profileAuthorAliases(for profile: DownloadProfile) -> Set<String> {
        var aliases = Set([normalizeProfileName(profile.name)].filter { !$0.isEmpty })
        let firstVideoID = contentID(from: profile.first_video_url)
        if !firstVideoID.isEmpty {
            for entry in downloadHistoryEntries() where entry.content_id == firstVideoID {
                let author = normalizeProfileName(entry.author)
                if !author.isEmpty {
                    aliases.insert(author)
                }
            }
        }
        let decodedProfileURL = profile.url.removingPercentEncoding ?? profile.url
        if let handle = decodedProfileURL
            .split(separator: "/")
            .first(where: { $0.hasPrefix("@") }) {
            aliases.insert(normalizeProfileName(String(handle)))
        }
        return aliases
    }

    private func downloadHistoryAuthor(for contentID: String) -> String? {
        for entry in downloadHistoryEntries().reversed() where entry.content_id == contentID {
            let author = normalizeProfileName(entry.author)
            if !author.isEmpty {
                return author
            }
        }
        return nil
    }

    private func platformKey(for url: String) -> String {
        switch platformName(for: url) {
        case "YouTube": return "youtube"
        case "哔哩哔哩": return "bilibili"
        case "抖音": return "douyin"
        case "小红书": return "xiaohongshu"
        case "Instagram": return "instagram"
        default: return ""
        }
    }

    private func contentID(from url: String) -> String {
        guard let components = URLComponents(string: url) else { return "" }
        if let value = components.queryItems?.first(where: { $0.name == "v" })?.value {
            return value
        }
        return components.url?.pathComponents.last(where: { $0 != "/" }) ?? ""
    }

    private func normalizeProfileName(_ value: String) -> String {
        value.lowercased()
            .replacingOccurrences(of: "@", with: "")
            .replacingOccurrences(of: "youtube-", with: "")
            .replacingOccurrences(of: "bilibili-", with: "")
            .replacingOccurrences(of: "哔哩哔哩-", with: "")
            .replacingOccurrences(of: "抖音-", with: "")
            .replacingOccurrences(of: "小红书-", with: "")
            .replacingOccurrences(of: "-", with: "")
            .replacingOccurrences(of: "_", with: "")
            .replacingOccurrences(of: " ", with: "")
    }

    private func updateDownloadProgress(from output: String, profileID: String) {
        var progress = profileProgress[profileID] ?? DownloadTaskProgress()
        var completedJobs = completedDownloadJobsByProfile[profileID] ?? []
        for line in output.split(separator: "\n").map(String.init) {
            if line.contains("profile.expand.login_wait") && !line.contains("login_waiting") {
                progress.status = "等待小红书登录"
                reportInfo("请在弹出的浏览器中完成小红书登录，App 最多等待 3 分钟")
            }
            if line.contains("profile.expand.login_complete") {
                progress.status = "登录成功，读取视频"
                reportInfo("小红书登录成功，正在读取主页视频")
            }
            if line.contains("profile.expand.login_timeout") {
                progress.status = "登录超时"
            }
            if line.contains("batch.download.start"), let jobs = integerField("jobs", in: line) {
                progress.total = jobs
                progress.status = jobs == 0 && progress.skippedDuplicates > 0 ? "没有新视频" : "下载中"
            }
            if line.contains("job.extract.start") {
                progress.status = "下载中"
            }
            if line.contains("job.download.skip_history") {
                progress.skippedDuplicates += 1
                progress.status = "检查去重"
            }
            if line.contains("job.download.complete") || line.contains("job.download.reuse") || line.contains("job.extract.failed") || line.contains("job.download.failed"),
               let job = integerField("job", in: line) {
                completedJobs.insert(job)
                progress.completed = completedJobs.count
                progress.status = line.contains("failed") ? "部分失败" : "下载中"
            }
        }
        completedDownloadJobsByProfile[profileID] = completedJobs
        profileProgress[profileID] = progress
    }

    private func finishActiveDownload(profileID: String, exitCode: Int32) {
        var progress = profileProgress[profileID] ?? DownloadTaskProgress()
        if exitCode == 0 {
            progress.completed = max(progress.completed, progress.total)
            if progress.completed == 0 && progress.skippedDuplicates > 0 {
                progress.status = "没有新视频"
            } else if progress.skippedDuplicates > 0 {
                progress.status = "已完成，含去重"
            } else {
                progress.status = "下载成功"
            }
        } else {
            progress.status = "下载失败"
        }
        profileProgress[profileID] = progress
        completedDownloadJobsByProfile.removeValue(forKey: profileID)
    }

    private func updateSingleDownloadProgress(from output: String) {
        for line in output.split(separator: "\n").map(String.init) {
            if line.contains("job.download.skip_history") || line.contains("job.download.reuse") {
                singleDownloadProgress = SingleDownloadProgress(phase: .duplicate, message: "已下载过，无需重复下载")
            } else if line.contains("job.download.complete") {
                singleDownloadProgress = SingleDownloadProgress(phase: .success, message: "下载成功")
            } else if line.contains("job.extract.failed") || line.contains("job.download.failed") {
                singleDownloadProgress = SingleDownloadProgress(phase: .failed, message: "下载失败，请查看日志")
            } else if line.contains("job.extract.start") || line.contains("ytdlp.download.start") {
                singleDownloadProgress = SingleDownloadProgress(phase: .downloading, message: "正在下载")
            }
        }
    }

    private func integerField(_ key: String, in line: String) -> Int? {
        guard let range = line.range(of: "\\b\(NSRegularExpression.escapedPattern(for: key))=(\\d+)", options: .regularExpression) else { return nil }
        return Int(line[range].split(separator: "=").last ?? "")
    }
}

private extension String {
    var shellQuoted: String {
        "'" + replacingOccurrences(of: "'", with: "'\\''") + "'"
    }

    var stableIDComponent: String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_"))
        let scalars = unicodeScalars.map { allowed.contains($0) ? Character($0) : "-" }
        return String(scalars).prefix(80).isEmpty ? UUID().uuidString : String(String(scalars).prefix(80))
    }
}

struct LogoMark: View {
    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 12)
                .fill(LinearGradient(colors: [Color(red: 0.10, green: 0.48, blue: 0.95), Color(red: 0.08, green: 0.72, blue: 0.62)], startPoint: .topLeading, endPoint: .bottomTrailing))
            Image(systemName: "play.rectangle.fill")
                .font(.system(size: 25, weight: .semibold))
                .foregroundStyle(.white)
            Image(systemName: "arrow.up.circle.fill")
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(.white)
                .offset(x: 14, y: -14)
        }
        .frame(width: 46, height: 46)
        .shadow(color: Color.black.opacity(0.14), radius: 8, y: 3)
    }
}

struct ContentView: View {
    @StateObject private var model = AppModel()
    @State private var section: WorkspaceSection = .download
    @State private var downloadMode: DownloadMode = .profiles
    @State private var publishMode: PublishMode = .single
    @State private var showAddProfile = false
    @State private var cookieExpanded = false
    @State private var showAddDownloadSchedule = false
    @State private var showAddPublishSchedule = false
    @State private var scheduleProfileDraft = ""
    @State private var scheduleIntervalDraft = 60
    @State private var scheduleStartDraft = "09:00"
    @State private var scheduleEndDraft = "23:00"
    @State private var schedulePublishDirectoriesDraft: [String] = []
    @State private var schedulePublishAccountIDDraft = ""
    @State private var schedulePublishOrderDraft = "sequential"
    @State private var schedulePublishScopeDraft = "author_global"
    @State private var schedulePublishGuildIDDraft = ""
    @State private var schedulePublishChannelIDDraft = ""
    @State private var schedulePublishFeedTypeDraft = 1
    @State private var schedulePublishLimitDraft = 1
    @State private var schedulePublishTitleTemplateDraft = "{title}"
    @State private var schedulePublishContentTemplateDraft = "{title}"
    @State private var schedulePublishStripTagsDraft = true
    @State private var schedulePublishTitleExclusionsDraft = ""
    @State private var schedulePublishTranslateDraft = false
    @State private var schedulePublishDeleteAfterDraft = true
    @State private var editingDownloadTask: ScheduledDownloadTask?
    @State private var editingPublishTask: ScheduledPublishTask?
    @State private var editingProfileNameID: String?
    @State private var downloadHistoryProfile: DownloadProfile?
    @State private var publishHistoryPage = 0
    @State private var publishHistoryFilter = "all"
    @State private var publishHistoryJumpText = ""
    @State private var showTencentTokenSettings = false
    @State private var showLogSearch = false
    @State private var logSearchText = ""
    @State private var logSearchKeyMonitor: Any?
    @FocusState private var logSearchFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            header
            if !model.noticeText.isEmpty {
                noticeBanner
            }
            Divider()
            HStack(spacing: 0) {
                sidebar
                Divider()
                mainContent
            }
        }
        .frame(minWidth: 1120, minHeight: 760)
        .onReceive(model.$config.dropFirst().debounce(for: .milliseconds(350), scheduler: RunLoop.main)) { _ in
            model.save()
        }
        .onAppear {
            model.startSchedulerMonitor()
            installLogSearchShortcut()
        }
        .onDisappear {
            removeLogSearchShortcut()
        }
        .sheet(isPresented: $showAddDownloadSchedule) {
            addDownloadScheduleSheet
        }
        .sheet(isPresented: $showAddPublishSchedule) {
            addPublishScheduleSheet
        }
        .sheet(item: $downloadHistoryProfile) { profile in
            profileDownloadHistorySheet(profile)
        }
    }

    private var header: some View {
        HStack(spacing: 12) {
            LogoMark()
            VStack(alignment: .leading, spacing: 3) {
                Text("Videocp Studio")
                    .font(.title2.bold())
                Text(model.status)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer()
            if !model.greetingText.isEmpty {
                Text(model.greetingText)
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Color.accentColor)
            }
            if model.updateAvailable {
                Label(model.updateStatusText, systemImage: "arrow.down.circle.fill")
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(Color.orange)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color.orange.opacity(0.12))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                Button {
                    model.openLatestRelease()
                } label: {
                    Label("打开更新", systemImage: "safari")
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.small)
                .tint(.orange)
            } else {
                Button {
                    model.checkForUpdates()
                } label: {
                    Label(model.checkingUpdate ? "检查中" : "检查更新", systemImage: "arrow.triangle.2.circlepath")
                }
                .buttonStyle(.borderless)
                .controlSize(.small)
                .disabled(model.checkingUpdate)
                .help(model.updateStatusText)
            }
            Text("v\(appVersion)")
                .font(.caption.weight(.semibold).monospacedDigit())
                .foregroundStyle(Color.accentColor)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color.accentColor.opacity(0.12))
                .clipShape(RoundedRectangle(cornerRadius: 6))
            Label("配置自动保存", systemImage: "checkmark.circle")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(16)
    }

    private var noticeBanner: some View {
        HStack(spacing: 10) {
            Image(systemName: model.noticeIsError ? "exclamationmark.triangle.fill" : "checkmark.circle.fill")
            Text(model.noticeText)
                .font(.caption)
                .lineLimit(2)
            Spacer()
            Button { model.dismissNotice() } label: {
                Image(systemName: "xmark")
            }
            .buttonStyle(.borderless)
        }
        .foregroundStyle(model.noticeIsError ? Color.red : Color.green)
        .padding(.horizontal, 16)
        .padding(.vertical, 9)
        .background((model.noticeIsError ? Color.red : Color.green).opacity(0.1))
    }

    private var sidebar: some View {
        VStack(alignment: .leading, spacing: 8) {
            ForEach(WorkspaceSection.allCases) { item in
                Button {
                    section = item
                } label: {
                    Label(item.title, systemImage: item.icon)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .buttonStyle(.borderless)
                .padding(.horizontal, 10)
                .padding(.vertical, 8)
                .background(section == item ? Color.accentColor.opacity(0.14) : Color.clear)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            Spacer()
            if model.hasActiveWork {
                ProgressView()
                    .controlSize(.small)
                    .frame(maxWidth: .infinity)
            }
        }
        .padding(12)
        .frame(width: 150)
        .background(Color(NSColor.windowBackgroundColor))
    }

    @ViewBuilder
    private var mainContent: some View {
        switch section {
        case .download:
            downloadView
        case .publish:
            publishView
        case .log:
            logView
        }
    }

    private func installLogSearchShortcut() {
        guard logSearchKeyMonitor == nil else { return }
        logSearchKeyMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { event in
            let key = event.charactersIgnoringModifiers?.lowercased() ?? ""
            let wantsFind = key == "f" && (event.modifierFlags.contains(.command) || event.modifierFlags.contains(.control))
            guard wantsFind else { return event }
            guard section == .log else { return event }
            showLogSearch = true
            DispatchQueue.main.async {
                logSearchFocused = true
            }
            return nil
        }
    }

    private func removeLogSearchShortcut() {
        if let monitor = logSearchKeyMonitor {
            NSEvent.removeMonitor(monitor)
            logSearchKeyMonitor = nil
        }
    }

    private var visibleLogText: String {
        let query = logSearchText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return model.logs }
        let lines = model.logs.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
        return lines
            .filter { $0.localizedCaseInsensitiveContains(query) }
            .joined(separator: "\n")
    }

    private var visibleLogMatchCount: Int {
        let query = logSearchText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return 0 }
        return model.logs
            .split(separator: "\n", omittingEmptySubsequences: false)
            .filter { String($0).localizedCaseInsensitiveContains(query) }
            .count
    }

    private func visiblePageItems(pageCount: Int, currentPage: Int) -> [Int?] {
        guard pageCount > 1 else { return [0] }
        var pages = Set<Int>()
        pages.insert(0)
        pages.insert(pageCount - 1)
        for page in max(0, currentPage - 2)...min(pageCount - 1, currentPage + 2) {
            pages.insert(page)
        }
        if currentPage < 4 {
            for page in 0...min(pageCount - 1, 4) { pages.insert(page) }
        }
        if currentPage > pageCount - 5 {
            for page in max(0, pageCount - 5)..<pageCount { pages.insert(page) }
        }
        let sorted = pages.sorted()
        var result: [Int?] = []
        var previous: Int?
        for page in sorted {
            if let previous, page - previous > 1 {
                result.append(nil)
            }
            result.append(page)
            previous = page
        }
        return result
    }

    private func jumpPublishHistory(to text: String, pageCount: Int) {
        guard let page = Int(text.trimmingCharacters(in: .whitespacesAndNewlines)) else { return }
        publishHistoryPage = min(max(page - 1, 0), max(pageCount - 1, 0))
    }

    private var downloadView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                titleRow("下载视频", icon: "arrow.down.circle.fill")
                HStack(spacing: 8) {
                    ForEach(DownloadMode.allCases) { mode in
                        Button {
                            downloadMode = mode
                        } label: {
                            Label(mode.title, systemImage: mode.icon)
                                .font(.headline)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 11)
                        }
                        .buttonStyle(.plain)
                        .foregroundStyle(downloadMode == mode ? Color.white : Color.primary)
                        .background(downloadMode == mode ? Color.accentColor : Color(NSColor.controlBackgroundColor))
                        .clipShape(RoundedRectangle(cornerRadius: 7))
                    }
                }
                .padding(6)
                .background(Color(NSColor.controlBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 8))
                downloadLocationPanel

                if downloadMode == .single {
                    panel {
                        HStack {
                            Text("单视频下载").font(.headline)
                            Spacer()
                            requirementPill(text: model.downloadDirectoryReady ? "保存位置已选择" : "先选择保存位置", ok: model.downloadDirectoryReady)
                        }
                        HStack(spacing: 12) {
                            field("视频链接", text: $model.config.download.single_video_url)
                            qualityPicker(
                                selection: $model.config.download.quality,
                                enabled: model.supportsQualitySelection(for: model.config.download.single_video_url)
                            )
                            Button { model.runSingleDownload() } label: {
                                Label("下载视频", systemImage: "arrow.down.circle.fill")
                            }
                            .disabled(model.busy || !model.downloadDirectoryReady)
                        }
                        Text("支持 YouTube、哔哩哔哩、抖音和小红书视频链接。部分平台可能要求先登录浏览器。")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        .onChange(of: model.config.download.single_video_url) {
                            model.resetSingleDownloadProgress()
                        }
                        singleDownloadStatus
                    }
                } else {
                    profileTaskList
                }
                panel {
                    DisclosureGroup(isExpanded: $cookieExpanded) {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("YouTube 下载被拦截时，把 cookies.txt 全文粘贴到这里。App 会把它写入本机受限权限文件供 yt-dlp 使用。")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            VStack(alignment: .leading, spacing: 4) {
                                Text("获取方法").font(.caption.bold())
                                Text("1. 在 Chrome 登录 YouTube，并保持登录状态。")
                                Text("2. 使用 “Get cookies.txt LOCALLY” 扩展，导出 youtube.com 的 cookies.txt。")
                                Text("3. 打开导出的文本文件，复制全部内容并粘贴到下方。")
                                Text("Cookie 相当于登录凭证，请勿分享给他人。失效后重新导出即可。")
                                    .foregroundStyle(.orange)
                            }
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            TextEditor(text: $model.config.download.youtube_cookies_text)
                                .font(.system(.caption, design: .monospaced))
                                .frame(minHeight: 150)
                                .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.secondary.opacity(0.16)))
                            HStack(spacing: 10) {
                                Button { model.saveYouTubeCookies() } label: {
                                    Label("保存 Cookie", systemImage: "checkmark.circle")
                                }
                                .buttonStyle(.borderedProminent)
                                if !model.youtubeCookieStatusText.isEmpty {
                                    statusPill(text: model.youtubeCookieStatusText, ok: model.config.download.youtube_cookies_text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty == false)
                                }
                                Spacer()
                                Button { model.checkYouTubeHelper() } label: {
                                    Label("检查下载组件", systemImage: "checkmark.seal")
                                }
                                .disabled(model.busy)
                            }
                        }
                        .padding(.top, 10)
                    } label: {
                        Label("YouTube Cookie", systemImage: "key.horizontal")
                            .font(.headline)
                    }
                }
            }
            .padding(22)
        }
        .sheet(isPresented: $showAddProfile) {
            VStack(alignment: .leading, spacing: 16) {
                Text("添加 UP 主").font(.title2.bold())
                VStack(alignment: .leading, spacing: 6) {
                    Text("主页 URL（YouTube / B站 / 抖音 / 小红书等）")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    TextEditor(text: $model.config.download.profile_url_draft)
                        .font(.system(.body, design: .monospaced))
                        .frame(minHeight: 150)
                        .overlay(RoundedRectangle(cornerRadius: 8).stroke(Color.secondary.opacity(0.16)))
                    Text("支持批量导入，一行一个主页链接。小红书主页按当前展示顺序下载，暂不支持热度排序。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                pickerField("下载方式", selection: $model.config.download.order)
                qualityPicker(selection: $model.config.download.quality, enabled: true)
                Text("每个 UP 主默认下载 30 条内容，添加后可在清单中单独修改。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                HStack {
                    Spacer()
                    Button("取消") { showAddProfile = false }
                    Button {
                        model.config.download.count = 30
                        showAddProfile = false
                        model.parseProfileDraft()
                    } label: {
                        Label("解析并添加", systemImage: "plus.circle.fill")
                    }
                    .keyboardShortcut(.defaultAction)
                    .disabled(model.busy || model.config.download.profile_url_draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
            .padding(22)
            .frame(width: 620)
        }
    }

    private var profileTaskList: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 12) {
                Text("UP 主清单").font(.headline)
                Text("\(model.config.download.profiles.count) 个来源")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                requirementPill(text: model.downloadDirectoryReady ? "可开始下载" : "先选择保存位置", ok: model.downloadDirectoryReady)
                Spacer()
                Button {
                    model.config.download.profile_url_draft = ""
                    model.config.download.order = "latest"
                    showAddProfile = true
                } label: {
                    Label("添加 UP 主", systemImage: "plus.circle.fill")
                        .font(.headline)
                }
                .buttonStyle(.borderedProminent)
                .disabled(model.busy)
            }
            .padding(.bottom, 12)

            if model.config.download.profiles.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "tray")
                        .font(.title2)
                        .foregroundStyle(.secondary)
                    Text("还没有 UP 主")
                        .font(.headline)
                    Text("点击右上角“添加 UP 主”创建第一个下载任务。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, minHeight: 150)
            } else {
                ForEach($model.config.download.profiles) { $profile in
                    profileTaskRow(profile: $profile)
                }
            }
        }
        .padding(14)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var downloadLocationPanel: some View {
        panel {
            HStack(spacing: 12) {
                Image(systemName: model.downloadDirectoryReady ? "folder.fill" : "folder.badge.questionmark")
                    .font(.title2)
                    .foregroundStyle(model.downloadDirectoryReady ? Color.green : Color.orange)
                    .frame(width: 28)
                VStack(alignment: .leading, spacing: 3) {
                    Text("保存位置")
                        .font(.headline)
                    Text(model.downloadDirectoryReady ? model.config.download.output_dir : "请选择一个本地文件夹后再开始下载")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                        .truncationMode(.middle)
                }
                Spacer()
                Button { model.chooseDownloadDirectory() } label: {
                    Label(model.downloadDirectoryReady ? "更换位置" : "选择文件夹", systemImage: "folder.badge.plus")
                }
                .buttonStyle(.borderedProminent)
                Button { model.openDownloadDirectory() } label: {
                    Label("打开", systemImage: "arrow.up.right.square")
                }
                .disabled(!model.downloadDirectoryReady)
            }
        }
    }

    private func profileTaskRow(profile: Binding<DownloadProfile>) -> some View {
        let current = profile.wrappedValue
        let progress = model.profileProgress[current.id] ?? DownloadTaskProgress()
        let scheduleTask = model.config.automation.download_tasks.first { $0.profile_id == current.id }
        let isDownloading = model.isProfileDownloading(current.id)
        return VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 12) {
                Image(systemName: "person.crop.rectangle.stack.fill")
                    .font(.title3)
                    .foregroundStyle(Color.accentColor)
                    .frame(width: 28, height: 28)
                if editingProfileNameID == current.id {
                    TextField("备注", text: profile.name)
                        .font(.headline)
                        .textFieldStyle(.roundedBorder)
                        .lineLimit(1)
                        .disabled(isDownloading)
                    Button {
                        editingProfileNameID = nil
                        model.save()
                    } label: {
                        Image(systemName: "checkmark.circle.fill")
                    }
                    .buttonStyle(.borderless)
                    .help("完成编辑")
                } else {
                    VStack(alignment: .leading, spacing: 3) {
                        Text(current.name.isEmpty ? "未命名 UP 主" : current.name)
                            .font(.headline)
                            .lineLimit(1)
                            .truncationMode(.tail)
                        HStack(spacing: 8) {
                            platformBadge(for: current.url)
                            Link(destination: URL(string: current.url) ?? URL(fileURLWithPath: "/")) {
                                Label("主页链接", systemImage: "arrow.up.right.square")
                            }
                                .help(current.url)
                            Label(
                                "本地 \(model.localVideoCount(for: current)) 个视频",
                                systemImage: "externaldrive.fill"
                            )
                        }
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    }
                    Button {
                        editingProfileNameID = current.id
                    } label: {
                        Image(systemName: "pencil")
                    }
                    .buttonStyle(.borderless)
                    .disabled(isDownloading)
                    .help("编辑备注")
                }
                Spacer()
                Button {
                    model.openProfileDownloadDirectory(current)
                } label: {
                    Label("打开目录", systemImage: "folder")
                }
                .buttonStyle(.borderless)
                .help("打开这个 UP 主已有视频所在的目录")
                Button {
                    downloadHistoryProfile = current
                } label: {
                    Label("已下载列表", systemImage: "list.bullet.rectangle")
                }
                .buttonStyle(.borderless)
                .help("查看用于下载去重的完整记录")
                if isDownloading {
                    statusPill(text: "下载中", ok: true)
                }
            }

            HStack(spacing: 12) {
                taskSettingCell("下载方式", icon: "arrow.up.arrow.down") {
                    if model.platformName(for: current.url) == "小红书" {
                        Text("最新")
                            .font(.subheadline.weight(.medium))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .help("小红书主页按页面当前展示顺序下载")
                    } else {
                        Picker("", selection: profile.order) {
                            Text("最新").tag("latest")
                            Text("热度").tag("popular")
                        }
                        .labelsHidden()
                        .pickerStyle(.segmented)
                        .controlSize(.small)
                        .disabled(isDownloading)
                    }
                }

                taskSettingCell("清晰度", icon: "display") {
                    qualityMenu(
                        selection: profile.quality,
                        enabled: model.supportsQualitySelection(for: current.url) && !isDownloading
                    )
                }

                taskSettingCell("下载数量", icon: "number") {
                    HStack(spacing: 7) {
                        TextField("数量", value: profile.count, format: .number)
                            .textFieldStyle(.roundedBorder)
                            .font(.subheadline.weight(.medium))
                            .monospacedDigit()
                            .frame(maxWidth: .infinity)
                            .onSubmit {
                                profile.wrappedValue.count = min(max(profile.wrappedValue.count, 1), 999)
                            }
                        Text("条")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .disabled(isDownloading)
                    .onChange(of: profile.wrappedValue.count) {
                        if profile.wrappedValue.count > 999 {
                            profile.wrappedValue.count = 999
                        } else if profile.wrappedValue.count < 1 {
                            profile.wrappedValue.count = 1
                        }
                    }
                }

                taskSettingCell("定时下载", icon: "clock") {
                    if let scheduleTask {
                        HStack(spacing: 8) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(model.scheduledDownloadStatus(for: scheduleTask))
                                    .font(.subheadline.weight(.medium))
                                    .lineLimit(1)
                                Text("每 \(scheduleTask.interval_minutes) 分钟 · \(scheduleTask.active_start)-\(scheduleTask.active_end)")
                                    .font(.caption2)
                                    .monospacedDigit()
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                            }
                            Spacer(minLength: 4)
                            Button {
                                model.setScheduledDownloadTaskEnabled(scheduleTask, enabled: !scheduleTask.enabled)
                            } label: {
                                Image(systemName: scheduleTask.enabled ? "pause.circle.fill" : "play.circle.fill")
                            }
                            .buttonStyle(.borderless)
                            .help(scheduleTask.enabled ? "暂停定时" : "开启定时")
                            Menu {
                                Button {
                                    editDownloadSchedule(scheduleTask, fallbackProfileID: current.id)
                                } label: {
                                    Label("修改定时", systemImage: "pencil")
                                }
                                Button(role: .destructive) {
                                    model.deleteScheduledDownloadTask(scheduleTask)
                                } label: {
                                    Label("删除定时", systemImage: "trash")
                                }
                            } label: {
                                Image(systemName: "ellipsis.circle")
                            }
                            .menuStyle(.borderlessButton)
                            .menuIndicator(.hidden)
                            .help("更多定时操作")
                        }
                    } else {
                        HStack {
                            Text("未设置")
                                .font(.subheadline.weight(.medium))
                                .foregroundStyle(.secondary)
                            Spacer()
                            Button {
                                editDownloadSchedule(nil, fallbackProfileID: current.id)
                            } label: {
                                Label("设置", systemImage: "clock.badge.plus")
                            }
                            .buttonStyle(.borderless)
                        }
                    }
                }
            }

            HStack(spacing: 12) {
                VStack(alignment: .leading, spacing: 5) {
                    HStack(spacing: 6) {
                        Text(progress.status)
                        if progress.total > 0 {
                            Text("\(progress.completed)/\(progress.total)")
                                .monospacedDigit()
                        }
                        if progress.skippedDuplicates > 0 {
                            Text("重复 \(progress.skippedDuplicates)")
                        }
                    }
                    .font(.caption)
                    .foregroundStyle(progress.status == "下载失败" ? Color.red : Color.secondary)
                    ProgressView(value: progress.fraction)
                }
                .frame(maxWidth: .infinity)

                if isDownloading {
                    Button { model.stopProfileDownload(current) } label: {
                        Label("停止", systemImage: "stop.circle.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .tint(.red)
                } else {
                    Button { model.runProfileDownload(current) } label: {
                        Label("开始下载", systemImage: "arrow.down.circle.fill")
                    }
                    .buttonStyle(.borderedProminent)
                    .disabled(!model.downloadDirectoryReady)
                }
                Button(role: .destructive) { model.deleteProfile(current) } label: {
                    Image(systemName: "trash")
                }
                .buttonStyle(.borderless)
                .disabled(isDownloading)
                .help("删除 UP 主")
            }
        }
        .padding(14)
        .background(Color(NSColor.windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color.secondary.opacity(0.14), lineWidth: 1)
        )
        .padding(.vertical, 5)
    }

    private func profileDownloadHistorySheet(_ profile: DownloadProfile) -> some View {
        let entries = model.downloadHistory(for: profile)
        return VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                platformBadge(for: profile.url)
                VStack(alignment: .leading, spacing: 2) {
                    Text(profile.name.isEmpty ? "未命名 UP 主" : profile.name)
                        .font(.title2.bold())
                    Text("下载去重记录 · \(entries.count) 条")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    model.openProfileDownloadDirectory(profile)
                } label: {
                    Label("打开下载目录", systemImage: "folder")
                }
                Button("完成") {
                    downloadHistoryProfile = nil
                }
                .keyboardShortcut(.defaultAction)
            }

            if entries.isEmpty {
                VStack(spacing: 8) {
                    Image(systemName: "list.bullet.rectangle")
                        .font(.largeTitle)
                        .foregroundStyle(.secondary)
                    Text("暂无下载记录")
                        .font(.headline)
                    Text("成功下载后会在这里留下永久去重记录。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                HStack(spacing: 12) {
                    Text("视频").frame(maxWidth: .infinity, alignment: .leading)
                    Text("下载时间").frame(width: 150, alignment: .leading)
                    Text("本地状态").frame(width: 88, alignment: .leading)
                    Text("操作").frame(width: 150, alignment: .leading)
                }
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 10)

                ScrollView {
                    LazyVStack(spacing: 0) {
                        ForEach(entries) { entry in
                            let exists = model.downloadHistoryFileExists(entry)
                            HStack(spacing: 12) {
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(entry.desc.isEmpty ? entry.content_id : entry.desc)
                                        .font(.subheadline.weight(.medium))
                                        .lineLimit(1)
                                    Text(entry.content_id)
                                        .font(.caption2.monospaced())
                                        .foregroundStyle(.secondary)
                                }
                                .frame(maxWidth: .infinity, alignment: .leading)
                                Text(entry.displayTime)
                                    .font(.caption.monospacedDigit())
                                    .foregroundStyle(.secondary)
                                    .frame(width: 150, alignment: .leading)
                                Label(
                                    exists ? "本地存在" : "文件已删除",
                                    systemImage: exists ? "checkmark.circle.fill" : "archivebox"
                                )
                                .font(.caption)
                                .foregroundStyle(exists ? Color.green : Color.secondary)
                                .frame(width: 88, alignment: .leading)
                                HStack(spacing: 8) {
                                    if model.isHistoryRedownloading(entry) {
                                        ProgressView()
                                            .controlSize(.small)
                                    } else {
                                        Button {
                                            model.redownloadHistoryEntry(entry, profile: profile)
                                        } label: {
                                            Image(systemName: "arrow.clockwise")
                                        }
                                        .buttonStyle(.borderless)
                                        .disabled(model.hasActiveHistoryRedownload)
                                        .help("按当前清晰度重新下载")
                                    }
                                    Button {
                                        model.revealDownloadHistoryFile(entry)
                                    } label: {
                                        Image(systemName: "magnifyingglass")
                                    }
                                    .buttonStyle(.borderless)
                                    .disabled(!exists)
                                    .help(exists ? "在 Finder 中显示" : "文件已经删除，去重记录仍保留")
                                    if let status = model.historyRedownloadStatus[entry.id] {
                                        Text(status)
                                            .font(.caption2)
                                            .foregroundStyle(status.contains("失败") ? Color.red : Color.secondary)
                                            .lineLimit(1)
                                            .help(status)
                                    }
                                }
                                .frame(width: 150, alignment: .leading)
                            }
                            .padding(.horizontal, 10)
                            .padding(.vertical, 9)
                            Divider()
                        }
                    }
                }
                .background(Color(NSColor.controlBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
        }
        .padding(20)
        .frame(width: 920, height: 600)
    }

    private func editDownloadSchedule(_ task: ScheduledDownloadTask?, fallbackProfileID: String) {
        editingDownloadTask = task
        scheduleProfileDraft = task?.profile_id ?? fallbackProfileID
        scheduleIntervalDraft = task?.interval_minutes ?? 60
        scheduleStartDraft = task.flatMap { $0.active_start.isEmpty ? nil : $0.active_start } ?? "09:00"
        scheduleEndDraft = task.flatMap { $0.active_end.isEmpty ? nil : $0.active_end } ?? "23:00"
        showAddDownloadSchedule = true
    }

    private var publishView: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                titleRow("发布到频道", icon: "paperplane.circle.fill")
                publishTabs
                panel {
                    VStack(alignment: .leading, spacing: 10) {
                        HStack {
                            Label("频道账号", systemImage: "person.crop.circle.badge.checkmark")
                                .font(.headline)
                            Spacer()
                            Button {
                                showTencentTokenSettings.toggle()
                            } label: {
                                Label(showTencentTokenSettings ? "收起" : "添加账号", systemImage: showTencentTokenSettings ? "chevron.up" : "plus")
                            }
                        }
                        if model.config.tencent_accounts.isEmpty {
                            Text("还没有频道账号，请添加并验证 Token。")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        } else {
                            ForEach(model.config.tencent_accounts) { account in
                                HStack {
                                    Image(systemName: account.verified ? "checkmark.seal.fill" : "exclamationmark.triangle")
                                        .foregroundStyle(account.verified ? Color.green : Color.orange)
                                    Text(account.displayName).font(.headline)
                                    Text(account.is_guild_author ? "创作者" : "非创作者")
                                        .font(.caption)
                                        .foregroundStyle(.secondary)
                                    Spacer()
                                    if model.config.publish.account_id == account.id {
                                        statusPill(text: "当前", ok: true)
                                    }
                                    Button(role: .destructive) {
                                        model.deleteTencentAccount(account)
                                    } label: {
                                        Image(systemName: "trash")
                                    }
                                    .buttonStyle(.borderless)
                                }
                            }
                        }
                        if showTencentTokenSettings || model.config.tencent_accounts.isEmpty {
                            HStack(spacing: 5) {
                                Text("还没有 Token？")
                                    .foregroundStyle(.secondary)
                                Link("前往腾讯频道开放平台获取", destination: URL(string: "https://connect.qq.com/")!)
                            }
                            .font(.caption)
                            TextField("账号备注，例如：全球视频精选", text: $model.tencentAccountNameInput)
                                .textFieldStyle(.roundedBorder)
                            SecureField("粘贴 QQ_AI_CONNECT_TOKEN，用于保存或更新本机登录凭证", text: $model.tencentTokenInput)
                                .textFieldStyle(.roundedBorder)
                            HStack(spacing: 10) {
                                Button {
                                    model.addTencentAccount()
                                } label: {
                                    Label("验证并添加账号", systemImage: "person.crop.circle.badge.plus")
                                }
                                .disabled(model.busy)
                                statusPill(text: model.tencentStatusText, ok: model.tencentStatusOK)
                                Spacer()
                            }
                            Text("Token 仅保存在本机配置中；每个发布任务会使用自己选择的账号。")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                if !model.config.tencent_accounts.isEmpty || publishMode == .history {
                    switch publishMode {
                    case .single:
                        singlePublishPanel
                    case .scheduled:
                        scheduledPublishTaskList
                    case .history:
                        publishHistoryPanel
                    }
                } else {
                    VStack(spacing: 8) {
                        Image(systemName: "lock.shield")
                            .font(.largeTitle)
                            .foregroundStyle(.secondary)
                        Text("验证频道登录后显示发布设置")
                            .font(.headline)
                        Text("先点击“检查登录”，确认当前账号可用。")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, minHeight: 180)
                }
            }
            .padding(22)
        }
    }

    private var publishTabs: some View {
        HStack(spacing: 8) {
            ForEach(PublishMode.allCases) { mode in
                Button {
                    publishMode = mode
                } label: {
                    Label(mode.title, systemImage: mode.icon)
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 10)
                }
                .buttonStyle(.plain)
                .foregroundStyle(publishMode == mode ? .white : .primary)
                .background(publishMode == mode ? Color.accentColor : Color(NSColor.controlBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 7))
            }
        }
        .padding(6)
        .background(Color(NSColor.windowBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var singlePublishPanel: some View {
        VStack(alignment: .leading, spacing: 18) {
            panel {
                Label("视频来源", systemImage: "folder.fill")
                    .font(.headline)
                HStack(spacing: 12) {
                    field("MP4 视频", text: $model.config.publish.input_video)
                    Button { model.choosePublishVideo() } label: {
                        Label("选择视频", systemImage: "film")
                    }
                    Button { model.openPathForPublishVideo() } label: {
                        Image(systemName: "arrow.up.right.square")
                    }
                }
                HStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("发布账号").font(.caption).foregroundStyle(.secondary)
                        Picker("", selection: $model.config.publish.account_id) {
                            ForEach(model.config.tencent_accounts) { account in
                                Text(account.displayName).tag(account.id)
                            }
                        }
                        .labelsHidden()
                    }
                    Spacer()
                }
                HStack(spacing: 12) {
                    VStack(alignment: .leading, spacing: 5) {
                        Text("发布范围").font(.caption).foregroundStyle(.secondary)
                        Picker("", selection: $model.config.publish.scope) {
                            Text("创作者全局贴").tag("author_global")
                            Text("频道内发帖").tag("channel")
                        }
                        .pickerStyle(.segmented)
                    }
                    VStack(alignment: .leading, spacing: 5) {
                        Text("帖子类型").font(.caption).foregroundStyle(.secondary)
                        Picker("", selection: $model.config.publish.feed_type) {
                            Text("短帖").tag(1)
                            Text("长帖").tag(2)
                        }
                        .pickerStyle(.segmented)
                    }
                }
                HStack(spacing: 12) {
                    field("频道ID", text: $model.config.publish.guild_id)
                    field("版块ID", text: $model.config.publish.channel_id)
                }
                .disabled(model.config.publish.scope != "channel")
            }
            panel {
                Label("帖子规则", systemImage: "slider.horizontal.3")
                    .font(.headline)
                HStack(spacing: 12) {
                    field("标题模板", text: $model.config.publish.title_template)
                    field("正文模板", text: $model.config.publish.content_template)
                }
                field("标题剔除词（多个用逗号分隔）", text: $model.config.publish.title_exclusions)
                HStack(spacing: 18) {
                    Toggle("剔除 # 和 @", isOn: $model.config.publish.strip_tags_mentions)
                    Toggle("标题翻译为简体中文", isOn: $model.config.publish.translate_title_zh_cn)
                    Toggle("手动发布成功后删除", isOn: $model.config.publish.delete_after_publish)
                    Spacer()
                }
                if model.config.publish.translate_title_zh_cn {
                    Text("发布前自动识别原语言并翻译标题，优先使用 Edge 翻译并自动回退；翻译失败时不会发布或删除视频。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Text("例如填写“凤凰解说王者荣耀”，标题末尾的“【凤凰解说王者荣耀】”会连同空括号一起移除。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Text("发布失败时会自动重试 2 次。最终仍失败的视频会保留在原目录，并记录为失败，不会进入已发布去重。")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            commandBar {
                Button { model.runPublish() } label: {
                    Label("开始发布", systemImage: "paperplane.circle.fill")
                }
                .keyboardShortcut("p", modifiers: [.command])
            }
        }
    }

    private var publishHistoryPanel: some View {
        let filtered = model.publishHistory.filter { entry in
            publishHistoryFilter == "all" || entry.displayStatus == publishHistoryFilter
        }
        let pageSize = 10
        let pageCount = max(1, Int(ceil(Double(filtered.count) / Double(pageSize))))
        let safePage = min(publishHistoryPage, pageCount - 1)
        let start = min(safePage * pageSize, filtered.count)
        let end = min(start + pageSize, filtered.count)
        let pageEntries = Array(filtered[start..<end])
        let retryableFailed = filtered.filter { !($0.isPublishSuccess) && model.canRetryPublish($0) && !model.isRetryPublishRunning($0) }
        return panel {
            HStack {
                Label("发布记录", systemImage: "clock.arrow.circlepath")
                    .font(.headline)
                Text("\(filtered.count) 条")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Picker("", selection: $publishHistoryFilter) {
                    Text("全部").tag("all")
                    Text("成功").tag("ok")
                    Text("失败").tag("failed")
                }
                .labelsHidden()
                .pickerStyle(.segmented)
                .frame(width: 180)
                .onChange(of: publishHistoryFilter) { publishHistoryPage = 0 }
                Button { model.loadPublishHistory() } label: {
                    Image(systemName: "arrow.clockwise")
                }
                .buttonStyle(.borderless)
                .help("刷新发布记录")
                Button {
                    model.retryFailedPublishes(retryableFailed)
                } label: {
                    Label("重新发布失败项", systemImage: "arrow.clockwise.circle")
                }
                .disabled(retryableFailed.isEmpty)
            }
            if filtered.isEmpty {
                Text(publishHistoryFilter == "failed" ? "还没有失败记录" : "还没有发布记录")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                ForEach(pageEntries) { entry in
                    HStack(spacing: 10) {
                        Image(systemName: entry.isPublishSuccess ? "checkmark.circle.fill" : "exclamationmark.circle.fill")
                            .foregroundStyle(entry.isPublishSuccess ? .green : .red)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(entry.desc.isEmpty ? entry.content_id : entry.desc)
                                .font(.caption)
                                .lineLimit(1)
                            Text(entry.isPublishSuccess ? entry.displayTime : "\(entry.displayTime) · \(entry.displayError)")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                        Spacer()
                        if entry.isPublishSuccess, let url = URL(string: entry.share_url), !entry.share_url.isEmpty {
                            Link("查看帖子", destination: url)
                                .font(.caption)
                        } else {
                            Button {
                                model.retryPublish(entry)
                            } label: {
                                Label(model.isRetryPublishRunning(entry) ? "发布中" : "重新发布", systemImage: "arrow.clockwise")
                            }
                            .font(.caption)
                            .disabled(!model.canRetryPublish(entry) || model.isRetryPublishRunning(entry))
                            .help(model.canRetryPublish(entry) ? "只重新发布这一条失败视频" : "本地视频不存在，无法重新发布")
                        }
                    }
                    .padding(.vertical, 2)
                }
                Divider()
                HStack(spacing: 8) {
                    Text("第 \(safePage + 1) / \(pageCount) 页")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Button { publishHistoryPage = max(0, safePage - 1) } label: {
                        Image(systemName: "chevron.left")
                    }
                    .disabled(safePage == 0)
                    ForEach(Array(visiblePageItems(pageCount: pageCount, currentPage: safePage).enumerated()), id: \.offset) { _, item in
                        if let page = item {
                            if page == safePage {
                                Button {
                                    publishHistoryPage = page
                                } label: {
                                    Text("\(page + 1)")
                                        .font(.caption.monospacedDigit())
                                        .frame(minWidth: 24)
                                }
                                .buttonStyle(.borderedProminent)
                                .controlSize(.small)
                            } else {
                                Button {
                                    publishHistoryPage = page
                                } label: {
                                    Text("\(page + 1)")
                                        .font(.caption.monospacedDigit())
                                        .frame(minWidth: 24)
                                }
                                .buttonStyle(.bordered)
                                .controlSize(.small)
                            }
                        } else {
                            Text("...")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    Button { publishHistoryPage = min(pageCount - 1, safePage + 1) } label: {
                        Image(systemName: "chevron.right")
                    }
                    .disabled(safePage >= pageCount - 1)
                    TextField("页码", text: $publishHistoryJumpText)
                        .textFieldStyle(.roundedBorder)
                        .frame(width: 56)
                        .onSubmit {
                            jumpPublishHistory(to: publishHistoryJumpText, pageCount: pageCount)
                        }
                    Button("跳转") {
                        jumpPublishHistory(to: publishHistoryJumpText, pageCount: pageCount)
                    }
                    .disabled(publishHistoryJumpText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
            }
        }
    }

    private var scheduledPublishTaskList: some View {
        panel {
            HStack {
                VStack(alignment: .leading, spacing: 3) {
                    Text("定时发布任务").font(.headline)
                    Text("从指定目录中选取视频，按顺序或随机持续发布。")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                Spacer()
                Button {
                    schedulePublishDirectoriesDraft = []
                    scheduleIntervalDraft = 60
                    scheduleStartDraft = "09:00"
                    scheduleEndDraft = "23:00"
                    schedulePublishOrderDraft = "sequential"
                    loadPublishScheduleSettings(from: model.config.publish)
                    editingPublishTask = nil
                    showAddPublishSchedule = true
                } label: {
                    Label("添加定时发布", systemImage: "plus.circle.fill")
                }
                .buttonStyle(.borderedProminent)
            }
            Divider()
            if model.config.automation.publish_tasks.isEmpty {
                scheduleEmptyState("还没有定时发布任务", detail: "创建任务后，可以从一个或多个目录持续发布视频。")
            } else {
                ForEach($model.config.automation.publish_tasks) { $task in
                    HStack(spacing: 12) {
                        Image(systemName: "paperplane.circle.fill")
                            .foregroundStyle(Color.accentColor)
                        VStack(alignment: .leading, spacing: 3) {
                            Text("\(task.directories.count) 个视频目录")
                                .font(.headline)
                            Text("\(task.order == "random" ? "随机发布" : "顺序发布") · 每 \(task.interval_minutes) 分钟执行")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                            Text("账号：\(model.config.tencent_accounts.first(where: { $0.id == task.account_id })?.displayName ?? "未选择")")
                                .font(.caption2)
                                .foregroundStyle(task.account_id.isEmpty ? Color.orange : .secondary)
                            Text([
                                task.scope == "channel" ? "频道内" : "创作者全局",
                                task.feed_type == 2 ? "长帖" : "短帖",
                                task.strip_tags_mentions ? "剔除#和@" : nil,
                                task.title_exclusions.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : "剔除指定词",
                                task.translate_title_zh_cn ? "翻译中文" : nil,
                                "每次 \(task.limit) 条"
                            ].compactMap { $0 }.joined(separator: " · "))
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                            Text(model.scheduledPublishNextRunText(for: task))
                                .font(.caption2.monospacedDigit())
                                .foregroundStyle(task.enabled ? Color.accentColor : .secondary)
                            Text(task.directories.first ?? "")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                                .lineLimit(1)
                        }
                        Spacer()
                        TextField("分钟", value: $task.interval_minutes, format: .number)
                            .textFieldStyle(.roundedBorder)
                            .frame(width: 54)
                            .help("执行间隔分钟")
                        scheduleWindowFields(start: $task.active_start, end: $task.active_end)
                        statusPill(
                            text: model.scheduledPublishStatus(for: task),
                            ok: task.enabled
                        )
                        Button {
                            model.setScheduledPublishTaskEnabled(task, enabled: !task.enabled)
                        } label: {
                            Image(systemName: task.enabled ? "stop.circle" : "play.circle")
                        }
                        .buttonStyle(.borderless)
                        .help(task.enabled ? "停止这个定时发布任务" : "开启这个定时发布任务")
                        Button {
                            editingPublishTask = task
                            schedulePublishDirectoriesDraft = task.directories
                            scheduleIntervalDraft = task.interval_minutes
                            scheduleStartDraft = task.active_start
                            scheduleEndDraft = task.active_end
                            schedulePublishOrderDraft = task.order
                            loadPublishScheduleSettings(from: task)
                            showAddPublishSchedule = true
                        } label: {
                            Image(systemName: "pencil")
                        }
                        .buttonStyle(.borderless)
                        .help("修改任务")
                        Button(role: .destructive) {
                            model.deleteScheduledPublishTask(task)
                        } label: {
                            Image(systemName: "trash")
                        }
                        .buttonStyle(.borderless)
                        .help("删除任务")
                    }
                    .padding(.vertical, 4)
                }
            }
        }
    }

    private func scheduleEmptyState(_ title: String, detail: String) -> some View {
        VStack(spacing: 6) {
            Image(systemName: "clock.badge.questionmark")
                .font(.title2)
                .foregroundStyle(.secondary)
            Text(title).font(.headline)
            Text(detail).font(.caption).foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, minHeight: 100)
    }

    private func scheduleWindowFields(start: Binding<String>, end: Binding<String>) -> some View {
        HStack(spacing: 5) {
            Text("每天")
            TextField("开始", text: start)
                .textFieldStyle(.roundedBorder)
                .frame(width: 54)
            Text("-")
            TextField("结束", text: end)
                .textFieldStyle(.roundedBorder)
                .frame(width: 54)
        }
        .font(.caption)
    }

    private var addDownloadScheduleSheet: some View {
        VStack(alignment: .leading, spacing: 18) {
            titleRow(editingDownloadTask == nil ? "设置 UP 主定时下载" : "修改 UP 主定时下载", icon: "arrow.down.circle.fill")
            VStack(alignment: .leading, spacing: 5) {
                Text("UP 主").font(.caption).foregroundStyle(.secondary)
                HStack {
                    Image(systemName: "person.crop.rectangle.stack")
                        .foregroundStyle(Color.accentColor)
                    Text(model.config.download.profiles.first(where: { $0.id == scheduleProfileDraft }).map { $0.name.isEmpty ? $0.url : $0.name } ?? "当前 UP 主")
                        .font(.headline)
                        .lineLimit(1)
                    Spacer()
                }
                .padding(10)
                .background(Color(NSColor.controlBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 8))
            }
            HStack(spacing: 12) {
                intField("执行间隔（分钟）", value: $scheduleIntervalDraft)
                field("每天开始", text: $scheduleStartDraft)
                field("每天结束", text: $scheduleEndDraft)
            }
            Spacer()
            HStack {
                Spacer()
                Button("取消") {
                    editingDownloadTask = nil
                    showAddDownloadSchedule = false
                }
                Button(editingDownloadTask == nil ? "添加任务" : "保存修改") {
                    if var task = editingDownloadTask {
                        task.interval_minutes = scheduleIntervalDraft
                        task.active_start = scheduleStartDraft
                        task.active_end = scheduleEndDraft
                        model.updateScheduledDownloadTask(task)
                    } else {
                        model.addScheduledDownloadTask(
                            profileID: scheduleProfileDraft.isEmpty
                                ? (model.config.download.profiles.first?.id ?? "")
                                : scheduleProfileDraft,
                            intervalMinutes: scheduleIntervalDraft,
                            activeStart: scheduleStartDraft,
                            activeEnd: scheduleEndDraft
                        )
                    }
                    editingDownloadTask = nil
                    showAddDownloadSchedule = false
                }
                .buttonStyle(.borderedProminent)
                .disabled(model.config.download.profiles.isEmpty)
            }
        }
        .padding(22)
        .frame(width: 620, height: 260)
        .onAppear {
            if scheduleProfileDraft.isEmpty {
                scheduleProfileDraft = model.config.download.profiles.first?.id ?? ""
            }
        }
    }

    private func loadPublishScheduleSettings(from settings: PublishSettings) {
        schedulePublishAccountIDDraft = settings.account_id
        schedulePublishScopeDraft = settings.scope
        schedulePublishGuildIDDraft = settings.guild_id
        schedulePublishChannelIDDraft = settings.channel_id
        schedulePublishFeedTypeDraft = settings.feed_type
        schedulePublishLimitDraft = settings.limit
        schedulePublishTitleTemplateDraft = settings.title_template
        schedulePublishContentTemplateDraft = settings.content_template
        schedulePublishStripTagsDraft = settings.strip_tags_mentions
        schedulePublishTitleExclusionsDraft = settings.title_exclusions
        schedulePublishTranslateDraft = settings.translate_title_zh_cn
        schedulePublishDeleteAfterDraft = settings.delete_after_publish
    }

    private func loadPublishScheduleSettings(from task: ScheduledPublishTask) {
        schedulePublishAccountIDDraft = task.account_id
        schedulePublishScopeDraft = task.scope
        schedulePublishGuildIDDraft = task.guild_id
        schedulePublishChannelIDDraft = task.channel_id
        schedulePublishFeedTypeDraft = task.feed_type
        schedulePublishLimitDraft = task.limit
        schedulePublishTitleTemplateDraft = task.title_template
        schedulePublishContentTemplateDraft = task.content_template
        schedulePublishStripTagsDraft = task.strip_tags_mentions
        schedulePublishTitleExclusionsDraft = task.title_exclusions
        schedulePublishTranslateDraft = task.translate_title_zh_cn
        schedulePublishDeleteAfterDraft = task.delete_after_publish
    }

    private func publishScheduleDraft(id: String = UUID().uuidString, enabled: Bool = true) -> ScheduledPublishTask {
        ScheduledPublishTask(
            id: id,
            directories: schedulePublishDirectoriesDraft,
            account_id: schedulePublishAccountIDDraft,
            interval_minutes: scheduleIntervalDraft,
            order: schedulePublishOrderDraft,
            enabled: enabled,
            active_start: scheduleStartDraft,
            active_end: scheduleEndDraft,
            scope: schedulePublishScopeDraft,
            guild_id: schedulePublishGuildIDDraft,
            channel_id: schedulePublishChannelIDDraft,
            feed_type: schedulePublishFeedTypeDraft,
            limit: schedulePublishLimitDraft,
            title_template: schedulePublishTitleTemplateDraft,
            content_template: schedulePublishContentTemplateDraft,
            strip_tags_mentions: schedulePublishStripTagsDraft,
            title_exclusions: schedulePublishTitleExclusionsDraft,
            translate_title_zh_cn: schedulePublishTranslateDraft,
            delete_after_publish: schedulePublishDeleteAfterDraft
        )
    }

    private var addPublishScheduleSheet: some View {
        VStack(alignment: .leading, spacing: 14) {
            titleRow(editingPublishTask == nil ? "添加定时发布" : "修改定时发布", icon: "paperplane.circle.fill")
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    panel {
                        Text("执行计划").font(.headline)
                        HStack(spacing: 12) {
                            VStack(alignment: .leading, spacing: 5) {
                                Text("选取方式").font(.caption).foregroundStyle(.secondary)
                                Picker("", selection: $schedulePublishOrderDraft) {
                                    Text("顺序发布").tag("sequential")
                                    Text("随机发布").tag("random")
                                }
                                .pickerStyle(.segmented)
                            }
                            intField("间隔（分钟）", value: $scheduleIntervalDraft)
                            field("每天开始", text: $scheduleStartDraft)
                            field("每天结束", text: $scheduleEndDraft)
                        }
                    }

                    panel {
                        HStack {
                            Text("视频目录").font(.headline)
                            Spacer()
                            Button {
                                if let path = model.chooseAutomationDirectory(),
                                   !schedulePublishDirectoriesDraft.contains(path) {
                                    schedulePublishDirectoriesDraft.append(path)
                                }
                            } label: {
                                Label("添加目录", systemImage: "plus.circle.fill")
                            }
                            .buttonStyle(.borderedProminent)
                        }
                        if schedulePublishDirectoriesDraft.isEmpty {
                            Text("请至少添加一个视频目录")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        ForEach(schedulePublishDirectoriesDraft, id: \.self) { path in
                            HStack {
                                Image(systemName: "folder")
                                    .foregroundStyle(Color.accentColor)
                                Text(path).font(.caption).lineLimit(1)
                                Spacer()
                                Button(role: .destructive) {
                                    schedulePublishDirectoriesDraft.removeAll { $0 == path }
                                } label: {
                                    Image(systemName: "trash")
                                }
                                .buttonStyle(.borderless)
                            }
                        }
                    }

                    panel {
                        Text("发布位置与帖子").font(.headline)
                        VStack(alignment: .leading, spacing: 5) {
                            Text("发布账号").font(.caption).foregroundStyle(.secondary)
                            Picker("", selection: $schedulePublishAccountIDDraft) {
                                Text("请选择账号").tag("")
                                ForEach(model.config.tencent_accounts) { account in
                                    Text(account.displayName).tag(account.id)
                                }
                            }
                            .labelsHidden()
                        }
                        HStack(spacing: 12) {
                            VStack(alignment: .leading, spacing: 5) {
                                Text("发布范围").font(.caption).foregroundStyle(.secondary)
                                Picker("", selection: $schedulePublishScopeDraft) {
                                    Text("创作者全局贴").tag("author_global")
                                    Text("频道内发帖").tag("channel")
                                }
                                .pickerStyle(.segmented)
                            }
                            VStack(alignment: .leading, spacing: 5) {
                                Text("帖子类型").font(.caption).foregroundStyle(.secondary)
                                Picker("", selection: $schedulePublishFeedTypeDraft) {
                                    Text("短帖").tag(1)
                                    Text("长帖").tag(2)
                                }
                                .pickerStyle(.segmented)
                            }
                            intField("每次发布", value: $schedulePublishLimitDraft)
                        }
                        HStack(spacing: 12) {
                            field("频道 ID", text: $schedulePublishGuildIDDraft)
                            field("版块 ID", text: $schedulePublishChannelIDDraft)
                        }
                        .disabled(schedulePublishScopeDraft != "channel")
                    }

                    panel {
                        Text("标题与正文").font(.headline)
                        HStack(spacing: 12) {
                            field("标题模板", text: $schedulePublishTitleTemplateDraft)
                            field("正文模板", text: $schedulePublishContentTemplateDraft)
                        }
                        field("标题剔除词（多个用逗号分隔）", text: $schedulePublishTitleExclusionsDraft)
                        HStack(spacing: 18) {
                            Toggle("剔除 # 和 @", isOn: $schedulePublishStripTagsDraft)
                            Toggle("标题翻译为简体中文", isOn: $schedulePublishTranslateDraft)
                            Toggle("成功后删除视频", isOn: $schedulePublishDeleteAfterDraft)
                            Spacer()
                        }
                    }
                }
            }
            HStack {
                Spacer()
                Button("取消") {
                    editingPublishTask = nil
                    showAddPublishSchedule = false
                }
                Button(editingPublishTask == nil ? "添加任务" : "保存修改") {
                    if let existing = editingPublishTask {
                        model.updateScheduledPublishTask(publishScheduleDraft(id: existing.id, enabled: existing.enabled))
                    } else {
                        model.addScheduledPublishTask(publishScheduleDraft())
                    }
                    editingPublishTask = nil
                    showAddPublishSchedule = false
                }
                .buttonStyle(.borderedProminent)
                .disabled(
                    schedulePublishDirectoriesDraft.isEmpty
                        || schedulePublishAccountIDDraft.isEmpty
                        || schedulePublishLimitDraft < 1
                        || (schedulePublishScopeDraft == "channel"
                            && (schedulePublishGuildIDDraft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                                || schedulePublishChannelIDDraft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty))
                )
            }
        }
        .padding(22)
        .frame(width: 840, height: 680)
    }

    private var logView: some View {
        VStack(alignment: .leading, spacing: 18) {
            HStack {
                Image(systemName: "terminal.fill")
                    .font(.title2)
                    .foregroundStyle(Color.accentColor)
                Text("日志")
                    .font(.title3.bold())
                Spacer()
                Text(model.droppedLogLineCount > 0 ? "最近 \(model.logLineCount) 行，已省略 \(model.droppedLogLineCount) 行" : "最近 \(model.logLineCount) 行")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                if showLogSearch {
                    HStack(spacing: 6) {
                        Image(systemName: "magnifyingglass")
                            .foregroundStyle(.secondary)
                        TextField("搜索日志", text: $logSearchText)
                            .textFieldStyle(.plain)
                            .focused($logSearchFocused)
                            .frame(width: 210)
                        if !logSearchText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty {
                            Text("\(visibleLogMatchCount)")
                                .font(.caption2.monospacedDigit())
                                .foregroundStyle(.secondary)
                        }
                        Button {
                            logSearchText = ""
                            showLogSearch = false
                        } label: {
                            Image(systemName: "xmark.circle.fill")
                        }
                        .buttonStyle(.borderless)
                    }
                    .padding(.horizontal, 9)
                    .padding(.vertical, 6)
                    .background(Color(NSColor.controlBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 8))
                } else {
                    Button {
                        showLogSearch = true
                        DispatchQueue.main.async {
                            logSearchFocused = true
                        }
                    } label: {
                        Label("搜索", systemImage: "magnifyingglass")
                    }
                    .keyboardShortcut("f", modifiers: [.command])
                }
                Button {
                    model.openLogDirectory()
                } label: {
                    Label("查看全部日志", systemImage: "folder")
                }
                Button {
                    model.clearLogs()
                } label: {
                    Label("清空", systemImage: "trash")
                }
                .disabled(model.logLineCount == 0)
            }
            logBox
        }
        .padding(22)
    }

    private var logBox: some View {
        ScrollView {
            Text(logBoxText)
                .font(.system(.caption, design: .monospaced))
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
                .padding(12)
        }
        .background(Color.black.opacity(0.05))
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .frame(maxHeight: .infinity)
    }

    private var logBoxText: String {
        if model.logs.isEmpty {
            return "暂无日志"
        }
        let query = logSearchText.trimmingCharacters(in: .whitespacesAndNewlines)
        if query.isEmpty {
            return model.logs
        }
        return visibleLogText.isEmpty ? "没有匹配的日志" : visibleLogText
    }

    private func titleRow(_ title: String, icon: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(Color.accentColor)
            Text(title)
                .font(.title3.bold())
            Spacer()
        }
    }

    private func panel<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            content()
        }
        .padding(14)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func commandBar<Content: View>(@ViewBuilder content: () -> Content) -> some View {
        HStack(spacing: 10) {
            content()
            Spacer()
        }
        .padding(.top, 2)
    }

    private func statusPill(text: String, ok: Bool) -> some View {
        Label(text, systemImage: ok ? "checkmark.circle.fill" : "info.circle")
            .font(.caption)
            .foregroundStyle(ok ? Color.green : Color.secondary)
            .lineLimit(1)
            .padding(.horizontal, 9)
            .padding(.vertical, 5)
            .background((ok ? Color.green : Color.secondary).opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func requirementPill(text: String, ok: Bool) -> some View {
        Label(text, systemImage: ok ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
            .font(.caption)
            .foregroundStyle(ok ? Color.green : Color.orange)
            .lineLimit(1)
            .padding(.horizontal, 9)
            .padding(.vertical, 5)
            .background((ok ? Color.green : Color.orange).opacity(0.12))
            .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var singleDownloadStatus: some View {
        HStack(spacing: 10) {
            Label(model.singleDownloadProgress.message, systemImage: singleDownloadStatusIcon)
                .font(.caption)
                .foregroundStyle(singleDownloadStatusColor)
            if model.singleDownloadProgress.canRedownload {
                Button {
                    model.runSingleDownload(forceRedownload: true)
                } label: {
                    Label("重新下载", systemImage: "arrow.clockwise")
                }
                .buttonStyle(.borderless)
                .disabled(model.busy)
            }
            Spacer()
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(singleDownloadStatusColor.opacity(0.1))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private var singleDownloadStatusIcon: String {
        switch model.singleDownloadProgress.phase {
        case .idle: "info.circle"
        case .downloading: "arrow.down.circle.fill"
        case .success: "checkmark.circle.fill"
        case .duplicate: "checkmark.circle"
        case .failed: "exclamationmark.triangle.fill"
        }
    }

    private var singleDownloadStatusColor: Color {
        switch model.singleDownloadProgress.phase {
        case .idle: .secondary
        case .downloading: .accentColor
        case .success: .green
        case .duplicate: .orange
        case .failed: .red
        }
    }

    private func field(_ title: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            TextField(title, text: text)
                .textFieldStyle(.roundedBorder)
        }
    }

    private func intField(_ title: String, value: Binding<Int>) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            TextField(title, value: value, format: .number)
                .textFieldStyle(.roundedBorder)
                .frame(minWidth: 90)
        }
    }

    private func pickerField(_ title: String, selection: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            Picker("", selection: selection) {
                Text("最新").tag("latest")
                Text("热度").tag("popular")
            }
            .pickerStyle(.segmented)
            .frame(width: 150)
        }
    }

    private func taskSettingCell<Content: View>(
        _ title: String,
        icon: String,
        @ViewBuilder content: () -> Content
    ) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            Label(title, systemImage: icon)
                .font(.caption.weight(.semibold))
                .foregroundStyle(.secondary)
                .lineLimit(1)
            content()
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(.horizontal, 11)
        .padding(.vertical, 9)
        .frame(maxWidth: .infinity, minHeight: 74, maxHeight: 74, alignment: .topLeading)
        .background(Color(NSColor.controlBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 7))
        .overlay(
            RoundedRectangle(cornerRadius: 7)
                .stroke(Color.secondary.opacity(0.12), lineWidth: 1)
        )
    }

    private func platformBadge(for url: String) -> some View {
        let platform = model.platformName(for: url)
        return Label(platform, systemImage: platformIcon(platform))
            .font(.caption.weight(.semibold))
            .foregroundStyle(Color.white)
            .lineLimit(1)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(platformColor(platform))
            .clipShape(RoundedRectangle(cornerRadius: 6))
            .accessibilityLabel("来源平台 \(platform)")
    }

    private func platformIcon(_ platform: String) -> String {
        switch platform {
        case "YouTube": return "play.rectangle.fill"
        case "哔哩哔哩": return "tv.fill"
        case "抖音": return "music.note"
        case "小红书": return "heart.text.square.fill"
        case "Instagram": return "camera.fill"
        default: return "globe"
        }
    }

    private func platformColor(_ platform: String) -> Color {
        switch platform {
        case "YouTube": return Color(red: 0.78, green: 0.03, blue: 0.05)
        case "哔哩哔哩": return Color(red: 0.12, green: 0.58, blue: 0.78)
        case "抖音": return Color(red: 0.04, green: 0.45, blue: 0.48)
        case "小红书": return Color(red: 1.00, green: 0.14, blue: 0.36)
        case "Instagram": return Color(red: 0.55, green: 0.20, blue: 0.64)
        default: return Color.secondary
        }
    }

    private func qualityMenu(selection: Binding<String>, enabled: Bool) -> some View {
        Picker("", selection: selection) {
            Text("平台最佳").tag("best")
            Text("2160P").tag("2160")
            Text("1080P").tag("1080")
            Text("720P").tag("720")
            Text("480P").tag("480")
        }
        .labelsHidden()
        .pickerStyle(.menu)
        .controlSize(.small)
        .frame(maxWidth: .infinity, alignment: .leading)
        .disabled(!enabled)
        .help(enabled ? "选择最高下载清晰度；不可用时自动降低" : "此平台目前只能下载页面提供的最佳版本")
        .onChange(of: enabled) {
            if !enabled {
                selection.wrappedValue = "best"
            }
        }
    }

    private func qualityPicker(selection: Binding<String>, enabled: Bool) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text("清晰度上限").font(.caption).foregroundStyle(.secondary)
            qualityMenu(selection: selection, enabled: enabled)
            .frame(width: 112, alignment: .leading)
        }
    }

    private func doubleField(_ title: String, value: Binding<Double>) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title).font(.caption).foregroundStyle(.secondary)
            TextField(title, value: value, format: .number)
                .textFieldStyle(.roundedBorder)
                .frame(minWidth: 90)
        }
    }
}

@main
struct VideocpSchedulerApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
        }
        .windowStyle(.titleBar)
    }
}
