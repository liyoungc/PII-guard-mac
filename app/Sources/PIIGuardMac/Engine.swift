import Foundation

/// Thin wrapper around the `piiguard` command line engine.
/// Every command prints one JSON object on stdout; progress goes to stderr.
enum Engine {
    static let appDir: URL = {
        if let home = ProcessInfo.processInfo.environment["PIIGUARD_HOME"] {
            return URL(fileURLWithPath: home)
        }
        return FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("PII-guard-mac")
    }()

    static var cli: URL {
        if let p = ProcessInfo.processInfo.environment["PIIGUARD_CLI"] { return URL(fileURLWithPath: p) }
        return appDir.appendingPathComponent("venv/bin/piiguard")
    }

    static var isInstalled: Bool { FileManager.default.isExecutableFile(atPath: cli.path) }

    struct Failure: LocalizedError {
        let message: String
        var errorDescription: String? { message }
    }

    static func run(_ args: [String], stdin: Data? = nil,
                    progress: (@Sendable (Int, Int) -> Void)? = nil) async throws -> [String: Any] {
        guard isInstalled else {
            throw Failure(message: "找不到引擎（\(cli.path)）。請重新執行安裝腳本 scripts/install.sh。")
        }
        return try await withCheckedThrowingContinuation { cont in
            DispatchQueue.global(qos: .userInitiated).async {
                let p = Process()
                p.executableURL = cli
                p.arguments = args
                let out = Pipe(), err = Pipe(), inp = Pipe()
                p.standardOutput = out; p.standardError = err; p.standardInput = inp
                err.fileHandleForReading.readabilityHandler = { h in
                    guard let progress, let s = String(data: h.availableData, encoding: .utf8) else { return }
                    for line in s.split(separator: "\n") {
                        if let d = line.data(using: .utf8),
                           let o = try? JSONSerialization.jsonObject(with: d) as? [String: Any],
                           let i = o["progress"] as? Int, let n = o["total"] as? Int {
                            progress(i, n)
                        }
                    }
                }
                do { try p.run() } catch {
                    cont.resume(throwing: Failure(message: "無法啟動引擎：\(error.localizedDescription)")); return
                }
                if let stdin { inp.fileHandleForWriting.write(stdin) }
                try? inp.fileHandleForWriting.close()
                let data = out.fileHandleForReading.readDataToEndOfFile()
                p.waitUntilExit()
                err.fileHandleForReading.readabilityHandler = nil
                guard let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                    cont.resume(throwing: Failure(message: "引擎沒有回傳結果（結束代碼 \(p.terminationStatus)）。")); return
                }
                if let e = obj["error"] as? String { cont.resume(throwing: Failure(message: e)); return }
                cont.resume(returning: obj)
            }
        }
    }
}

struct Entity: Identifiable, Hashable {
    var id: String { value }
    var value: String
    var type: String
    var source: String
    var count: Int
    var replacement: String
    var accepted = true

    init?(_ d: [String: Any]) {
        guard let v = d["value"] as? String, let t = d["type"] as? String else { return nil }
        value = v; type = t
        source = d["source"] as? String ?? "manual"
        count = d["count"] as? Int ?? 0
        replacement = d["replacement"] as? String ?? ""
    }
    init(manual value: String) {
        self.value = value; type = "person"; source = "manual"; count = 0; replacement = ""
    }
    var json: [String: Any] { ["value": value, "type": type, "source": source, "count": count] }
}

struct ModelInfo: Identifiable {
    var id: String
    var family: String, params: String, license: String
    var diskGB: Double
    var tierGB: Int
    var downloaded: Bool, fits: Bool
    var recommendedFor: [Int]
    var recall: Double?, precision: Double?, memoryGB: Double?
    var charsPerSec: Int?

    init?(_ d: [String: Any]) {
        guard let i = d["id"] as? String else { return nil }
        id = i
        family = d["family"] as? String ?? ""; params = d["params"] as? String ?? ""
        license = d["license"] as? String ?? ""
        diskGB = d["disk_gb"] as? Double ?? 0; tierGB = d["tier_gb"] as? Int ?? 0
        downloaded = d["downloaded"] as? Bool ?? false; fits = d["fits_this_mac"] as? Bool ?? false
        recommendedFor = d["recommended_for"] as? [Int] ?? []
        if let m = d["measured"] as? [String: Any] {
            recall = m["recall"] as? Double; precision = m["precision"] as? Double
            memoryGB = m["memory_gb"] as? Double; charsPerSec = m["chars_per_sec"] as? Int
        }
    }
    var shortName: String { id.split(separator: "/").last.map(String.init) ?? id }
}
