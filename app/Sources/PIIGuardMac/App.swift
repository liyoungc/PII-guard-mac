import AppKit
import SwiftUI

/// Labels show the mask character that is actually configured, so the menu
/// never promises one character while the output uses another.
func modeLabels(_ m: String) -> [(String, String)] {
    [
        ("keep_surname", "留姓（王小明 → 王\(m)\(m)）"),
        ("keep_surname_numbered", "留姓＋編號（同姓不同人可區分）"),
        ("full", "全遮（王小明 → \(m)\(m)\(m)）"),
        ("code", "代號（王小明 → 人員A）"),
    ]
}
let categoryLabels: [(String, String)] = [
    ("person", "人名（需要模型）"),
    ("tw_id", "身分證／居留證字號"),
    ("phone", "電話"),
    ("email", "Email"),
    ("mrn", "病歷號（6–10 碼數字，容易誤判，請搭配人工確認）"),
]

@main
struct PIIGuardApp: App {
    @StateObject private var state = AppState.shared

    init() {
        Task { @MainActor in AppState.shared.start() }
    }

    var body: some Scene {
        MenuBarExtra {
            MenuContent().environmentObject(state)
        } label: {
            Image(systemName: icon)
        }
        .menuBarExtraStyle(.menu)

        Window("確認遮蔽項目", id: "review") {
            ReviewView().environmentObject(state)
        }
        .windowResizability(.contentMinSize)
        .defaultSize(width: 640, height: 560)

        Window("處理結果", id: "results") {
            ResultsView().environmentObject(state)
        }
        .defaultSize(width: 560, height: 360)

        Window("PII Guard 設定", id: "settings") {
            SettingsView().environmentObject(state)
        }
        .windowResizability(.contentSize)
    }

    private var icon: String {
        if state.busyText != nil { return "hourglass" }
        switch state.serverState {
        case .ready: return "eye.slash.fill"
        case .loading: return "arrow.down.circle"
        case .stopped: return "eye.slash"
        }
    }
}

struct MenuContent: View {
    @EnvironmentObject var state: AppState
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        let _ = (WindowOpener.action = openWindow)
        if !Engine.isInstalled {
            Text("尚未安裝引擎：請執行 scripts/install.sh")
        }
        Text(statusLine)
        if let busy = state.busyText { Text(busy) }
        Divider()
        Button("選擇檔案去識別化…") { state.pickFiles() }
            .keyboardShortcut("o")
            .disabled(state.busyText != nil || state.review != nil)
        Divider()
        switch state.serverState {
        case .stopped:
            Button("載入模型") { Task { await state.loadModel() } }
        case .loading:
            Button("取消載入") { Task { await state.unloadModel() } }
        case .ready:
            Button("卸載模型（釋放記憶體）") { Task { await state.unloadModel() } }
        }
        Button("設定…") { WindowOpener.open("settings") }.keyboardShortcut(",")
        if !state.results.isEmpty {
            Button("處理結果…") { WindowOpener.open("results") }
        }
        Divider()
        Button("結束") {
            Task {
                await state.unloadModel()  // never leave a model resident after quitting
                NSApp.terminate(nil)
            }
        }
        .keyboardShortcut("q")
    }

    private var statusLine: String {
        let name = (state.loadedModel ?? state.selectedModel).map { $0.split(separator: "/").last.map(String.init) ?? $0 }
        switch state.serverState {
        case .ready: return "模型已載入：\(name ?? "")"
        case .loading: return "模型載入中：\(name ?? "")"
        case .stopped: return name.map { "模型未載入（已選：\($0)）" } ?? "模型未載入"
        }
    }
}

struct ResultsView: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        List(state.results) { r in
            VStack(alignment: .leading, spacing: 4) {
                HStack {
                    Image(systemName: r.verified ? "checkmark.seal.fill" : "exclamationmark.triangle.fill")
                        .foregroundStyle(r.verified ? .green : .orange)
                    Text(r.output.lastPathComponent).fontWeight(.medium)
                    Spacer()
                    Button("在 Finder 顯示") { NSWorkspace.shared.activateFileViewerSelecting([r.output]) }
                }
                Text("取代 \(r.replaced) 處，清除 \(r.metadataCleared) 個檔案屬性欄位。" +
                     (r.verified ? "複查通過：輸出檔內已找不到任何已確認的原文。"
                                 : "複查未通過：仍有殘留 → \(r.residual.keys.sorted().joined(separator: "、"))"))
                    .font(.callout).foregroundStyle(.secondary)
                if let m = r.mapping {
                    Text("對照表：\(m.lastPathComponent)（含原始姓名，請妥善保管）")
                        .font(.callout).foregroundStyle(.orange)
                }
            }
            .padding(.vertical, 4)
        }
        .frame(minWidth: 520, minHeight: 240)
    }
}
