import AppKit
import SwiftUI

enum ServerState: String { case stopped, loading, ready }

struct ReviewJob: Identifiable {
    let id = UUID()
    let file: URL
    var entities: [Entity]
    var whitelisted: [String]
    var discarded: Int
}

struct JobResult: Identifiable {
    let id = UUID()
    let file: URL
    let output: URL
    let replaced: Int
    let verified: Bool
    let residual: [String: Int]
    let mapping: URL?
    let metadataCleared: Int
}

@MainActor
final class AppState: ObservableObject {
    static let shared = AppState()

    // settings (mirrors config.json, shared with the CLI)
    @Published var cfg: [String: Any] = [:]
    // model server
    @Published var serverState: ServerState = .stopped
    @Published var loadedModel: String?
    @Published var models: [ModelInfo] = []
    @Published var ramGB = 0
    @Published var recommended: String?
    @Published var measuredOn: String?
    // work
    @Published var busyText: String?
    @Published var review: ReviewJob?
    @Published var results: [JobResult] = []
    @Published var lastError: String? {
        didSet {
            guard let message = lastError else { return }
            NSApp.activate(ignoringOtherApps: true)
            let alert = NSAlert()
            alert.messageText = "PII Guard"
            alert.informativeText = message
            alert.runModal()
            lastError = nil
        }
    }
    private var queue: [URL] = []
    private var timer: Timer?

    var configURL: URL { Engine.appDir.appendingPathComponent("config.json") }

    func start() {
        Task {
            await reloadConfig()
            await refreshModels()
            await refreshStatus()
        }
        timer = Timer.scheduledTimer(withTimeInterval: 3, repeats: true) { _ in
            Task { @MainActor in await AppState.shared.refreshStatus() }
        }
    }

    // MARK: settings
    func reloadConfig() async {
        if let c = try? await Engine.run(["config", "show"]) { cfg = c }
    }

    func set(_ key: String, _ value: Any) {
        cfg[key] = value
        saveConfig()
        // A setting changed while a review list is open: recompute what the list
        // shows, so what is displayed is always what will be written.
        if review != nil, ["mode", "mask_char"].contains(key) {
            Task { await refreshPreview() }
        }
    }

    func setCategory(_ key: String, _ on: Bool) {
        var c = cfg["categories"] as? [String: Any] ?? [:]
        c[key] = on
        set("categories", c)
    }

    func category(_ key: String) -> Bool { (cfg["categories"] as? [String: Any])?[key] as? Bool ?? false }
    func string(_ key: String, _ fallback: String = "") -> String { cfg[key] as? String ?? fallback }
    func bool(_ key: String, _ fallback: Bool = false) -> Bool { cfg[key] as? Bool ?? fallback }
    func list(_ key: String) -> [String] { cfg[key] as? [String] ?? [] }

    private func saveConfig() {
        try? FileManager.default.createDirectory(at: Engine.appDir, withIntermediateDirectories: true)
        if let d = try? JSONSerialization.data(withJSONObject: cfg, options: [.prettyPrinted, .sortedKeys]) {
            try? d.write(to: configURL, options: .atomic)
        }
    }

    var selectedModel: String? { (cfg["model"] as? String) ?? recommended }

    // MARK: model server
    func refreshModels() async {
        guard let m = try? await Engine.run(["models"]) else { return }
        ramGB = m["ram_gb"] as? Int ?? 0
        recommended = m["recommended"] as? String
        measuredOn = m["measured_on"] as? String
        models = (m["models"] as? [[String: Any]] ?? []).compactMap(ModelInfo.init)
    }

    func refreshStatus() async {
        guard Engine.isInstalled, let s = try? await Engine.run(["server", "status"]) else { return }
        serverState = ServerState(rawValue: s["state"] as? String ?? "stopped") ?? .stopped
        loadedModel = s["model"] as? String
    }

    func loadModel() async {
        guard let model = selectedModel else {
            lastError = "尚未選擇模型。請到「設定 › 模型」選一個。"; return
        }
        do {
            _ = try await Engine.run(["server", "start", "--model", model])
            await refreshStatus()
        } catch { lastError = error.localizedDescription }
    }

    func unloadModel() async {
        _ = try? await Engine.run(["server", "stop"])
        await refreshStatus()
    }

    private func ensureModelReady() async -> Bool {
        guard category("person") else { return true }  // pattern-only runs need no model
        if serverState == .stopped { await loadModel() }
        while serverState == .loading {
            busyText = "載入模型中…（第一次會下載模型，可能需要數分鐘）"
            try? await Task.sleep(nanoseconds: 2_000_000_000)
            await refreshStatus()
        }
        if serverState != .ready {
            lastError = "模型載入失敗。請看記錄檔：\(Engine.appDir.path)/server.log"
        }
        return serverState == .ready
    }

    // MARK: processing
    func pickFiles() {
        NSApp.activate(ignoringOtherApps: true)
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = true
        panel.canChooseDirectories = false
        panel.message = "選擇要去識別化的文件（原檔不會被更動）"
        if panel.runModal() == .OK { enqueue(panel.urls) }
    }

    func enqueue(_ urls: [URL]) {
        queue.append(contentsOf: urls)
        if busyText == nil, review == nil { Task { await next() } }
    }

    private func next() async {
        guard !queue.isEmpty else { busyText = nil; return }
        let file = queue.removeFirst()
        busyText = "準備中：\(file.lastPathComponent)"
        guard await ensureModelReady() else { busyText = nil; queue.removeAll(); return }
        do {
            busyText = "偵測中：\(file.lastPathComponent)"
            let name = file.lastPathComponent
            let r = try await Engine.run(["scan", file.path]) { i, n in
                Task { @MainActor in AppState.shared.busyText = "偵測中：\(name)（\(i)/\(n)）" }
            }
            let ents = (r["entities"] as? [[String: Any]] ?? []).compactMap(Entity.init)
            let job = ReviewJob(file: file, entities: ents,
                                whitelisted: r["whitelisted"] as? [String] ?? [],
                                discarded: r["discarded_model_outputs"] as? Int ?? 0)
            busyText = nil
            if bool("review", true) {
                review = job
                WindowOpener.open("review")
            } else {
                await write(job)
            }
        } catch {
            lastError = "\(file.lastPathComponent)：\(error.localizedDescription)"
            busyText = nil
            await next()
        }
    }

    /// Recompute the replacement column after the reviewer edits the list.
    func refreshPreview() async {
        guard var job = review else { return }
        let body = try? JSONSerialization.data(withJSONObject: ["entities": job.entities.map(\.json)])
        guard let r = try? await Engine.run(["preview"], stdin: body),
              let list = r["entities"] as? [[String: Any]] else { return }
        let repl = Dictionary(uniqueKeysWithValues: list.compactMap { d -> (String, String)? in
            guard let v = d["value"] as? String, let x = d["replacement"] as? String else { return nil }
            return (v, x)
        })
        for i in job.entities.indices { job.entities[i].replacement = repl[job.entities[i].value] ?? "" }
        if review?.id == job.id { review = job }
    }

    func write(_ job: ReviewJob, acceptAll: Bool = false) async {
        let chosen = job.entities.filter { acceptAll || $0.accepted }
        review = nil
        busyText = "寫出中：\(job.file.lastPathComponent)"
        do {
            let body = try JSONSerialization.data(withJSONObject: ["entities": chosen.map(\.json)])
            let r = try await Engine.run(["apply", job.file.path, "--decisions", "-"], stdin: body)
            let res = JobResult(
                file: job.file,
                output: URL(fileURLWithPath: r["output"] as? String ?? ""),
                replaced: r["replaced"] as? Int ?? 0,
                verified: r["verified"] as? Bool ?? false,
                residual: r["residual"] as? [String: Int] ?? [:],
                mapping: (r["mapping"] as? String).map { URL(fileURLWithPath: $0) },
                metadataCleared: r["metadata_fields_cleared"] as? Int ?? 0)
            results.insert(res, at: 0)
            WindowOpener.open("results")
        } catch {
            lastError = "\(job.file.lastPathComponent)：\(error.localizedDescription)"
        }
        busyText = nil
        await next()
    }

    func skipCurrent() {
        review = nil
        Task { await next() }
    }

    func addToWhitelist(_ value: String) {
        var wl = list("whitelist")
        if !wl.contains(value) { wl.append(value); set("whitelist", wl) }
    }
}

/// Lets non-view code open SwiftUI windows (the menu bar app has no main window).
@MainActor
enum WindowOpener {
    static var action: OpenWindowAction?
    static func open(_ id: String) {
        NSApp.activate(ignoringOtherApps: true)
        action?(id: id)
    }
}
