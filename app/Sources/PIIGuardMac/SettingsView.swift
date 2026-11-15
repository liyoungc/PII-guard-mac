import SwiftUI

struct SettingsView: View {
    var body: some View {
        TabView {
            ModelTab().tabItem { Label("模型", systemImage: "cpu") }
            MaskTab().tabItem { Label("遮蔽", systemImage: "eye.slash") }
            ListsTab().tabItem { Label("白名單", systemImage: "list.bullet") }
            AboutTab().tabItem { Label("說明", systemImage: "info.circle") }
        }
        .frame(width: 720, height: 520)
        .padding(12)
    }
}

private struct ModelTab: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("這台 Mac 有 \(state.ramGB) GB 記憶體。" + (state.recommended.map {
                "實測後建議：\($0.split(separator: "/").last.map(String.init) ?? $0)"
            } ?? "尚無實測建議。"))
                .font(.headline)
            Text("召回率＝合成病安通報語料中的人名被找到的比例（越高越不會漏遮，最重要）。精確率＝找到的項目中確實是人名的比例。"
                 + (state.measuredOn.map { "量測環境：\($0)。" } ?? "")
                 + "較小的模型較容易漏抓，請務必人工確認。")
                .font(.callout).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)

            List {
                ForEach(state.models) { m in
                    HStack(alignment: .top) {
                        Image(systemName: state.selectedModel == m.id ? "largecircle.fill.circle" : "circle")
                            .foregroundStyle(state.selectedModel == m.id ? Color.accentColor : .secondary)
                        VStack(alignment: .leading, spacing: 2) {
                            HStack {
                                Text(m.shortName).fontWeight(.medium)
                                ForEach(m.recommendedFor, id: \.self) { t in
                                    Text("\(t) GB 建議").font(.caption2).padding(.horizontal, 5).padding(.vertical, 1)
                                        .background(Color.green.opacity(0.2), in: Capsule())
                                }
                                if !m.fits {
                                    Text("超過本機建議").font(.caption2).foregroundStyle(.orange)
                                }
                            }
                            Text(detail(m)).font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        Text(m.downloaded ? "已下載" : "未下載（\(String(format: "%.1f", m.diskGB)) GB）")
                            .font(.caption).foregroundStyle(.secondary)
                    }
                    .contentShape(Rectangle())
                    .onTapGesture { state.set("model", m.id) }
                }
            }

            HStack {
                switch state.serverState {
                case .stopped: Text("狀態：未載入")
                case .loading: ProgressView().controlSize(.small); Text("載入中…（第一次會下載模型）")
                case .ready: Text("狀態：已載入 \(state.loadedModel ?? "")")
                }
                Spacer()
                Button("重新整理") { Task { await state.refreshModels() } }
                Button("卸載") { Task { await state.unloadModel() } }.disabled(state.serverState == .stopped)
                Button("載入所選模型") { Task { await state.loadModel() } }
                    .disabled(state.selectedModel == nil ||
                              (state.serverState != .stopped && state.loadedModel == state.selectedModel))
            }
        }
        .padding(8)
    }

    private func detail(_ m: ModelInfo) -> String {
        var parts = ["\(m.family) \(m.params)", "適用 \(m.tierGB) GB 以上", m.license]
        if let r = m.recall, let p = m.precision {
            parts.append("召回率 \(Int((r * 100).rounded()))%／精確率 \(Int((p * 100).rounded()))%")
        } else {
            parts.append("尚未實測")
        }
        if let c = m.charsPerSec { parts.append("約 \(c) 字／秒") }
        if let g = m.memoryGB, g > 0 { parts.append("記憶體 \(String(format: "%.1f", g)) GB") }
        return parts.joined(separator: " · ")
    }
}

private struct MaskTab: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        Form {
            Picker("人名遮蔽模式", selection: Binding(
                get: { state.string("mode", "keep_surname") }, set: { state.set("mode", $0) })) {
                ForEach(modeLabels, id: \.0) { Text($0.1).tag($0.0) }
            }
            HStack {
                TextField("遮蔽字元", text: Binding(
                    get: { state.string("mask_char", "○") },
                    set: { if let c = $0.last { state.set("mask_char", String(c)) } }))
                    .frame(width: 140)
                ForEach(["○", "Ｏ", "＊", "●", "Ｘ"], id: \.self) { c in
                    Button(c) { state.set("mask_char", c) }
                }
            }
            Section("要遮蔽的類別") {
                ForEach(categoryLabels, id: \.0) { key, label in
                    Toggle(label, isOn: Binding(get: { state.category(key) }, set: { state.setCategory(key, $0) }))
                }
                VStack(alignment: .leading) {
                    Text("自訂樣式（每行一條：名稱=正規表示式，例如　員工編號=E\\d{5}）").font(.callout)
                    TextEditor(text: Binding(get: { customText }, set: { setCustom($0) }))
                        .font(.system(.body, design: .monospaced)).frame(height: 54)
                        .border(Color.secondary.opacity(0.3))
                }
            }
            Section("流程") {
                Toggle("寫檔前先顯示確認清單（建議開啟）", isOn: Binding(
                    get: { state.bool("review", true) }, set: { state.set("review", $0) }))
                Toggle("同時輸出對照表（原文 → 取代文字；含原始姓名，請另外保管）", isOn: Binding(
                    get: { state.bool("write_mapping") }, set: { state.set("write_mapping", $0) }))
                Toggle("清除檔案屬性中的作者、最後修改者、註解作者", isOn: Binding(
                    get: { state.bool("scrub_metadata", true) }, set: { state.set("scrub_metadata", $0) }))
            }
        }
        .formStyle(.grouped)
    }

    private var customText: String {
        (state.cfg["custom_patterns"] as? [[String: Any]] ?? []).compactMap { d in
            guard let p = d["pattern"] as? String else { return nil }
            return "\(d["name"] as? String ?? "自訂")=\(p)"
        }.joined(separator: "\n")
    }

    private func setCustom(_ text: String) {
        let rows: [[String: Any]] = text.split(separator: "\n").compactMap { line in
            let parts = line.split(separator: "=", maxSplits: 1).map(String.init)
            guard parts.count == 2, !parts[1].isEmpty else { return nil }
            return ["name": parts[0], "pattern": parts[1]]
        }
        state.set("custom_patterns", rows)
    }
}

private struct ListsTab: View {
    @EnvironmentObject var state: AppState

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Toggle("使用內建醫療白名單（科別、職稱、「行政」、以人名命名的疾病等）", isOn: Binding(
                get: { state.bool("use_default_whitelist", true) }, set: { state.set("use_default_whitelist", $0) }))
            HStack(alignment: .top, spacing: 12) {
                editor("白名單：不需遮蔽（每行一個）", key: "whitelist")
                editor("一定要遮蔽（每行一個，視為人名）", key: "blacklist")
            }
            Text("白名單為完全相符才略過。確認清單上的「加入白名單」也會寫到這裡。")
                .font(.caption).foregroundStyle(.secondary)
        }
        .padding(8)
    }

    private func editor(_ title: String, key: String) -> some View {
        VStack(alignment: .leading) {
            Text(title).font(.callout)
            TextEditor(text: Binding(
                get: { state.list(key).joined(separator: "\n") },
                set: { state.set(key, $0.split(separator: "\n").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }) }))
                .border(Color.secondary.opacity(0.3))
        }
    }
}

private struct AboutTab: View {
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 10) {
                Text("支援的格式").font(.headline)
                Text("Word（.docx）、Excel（.xlsx）、PowerPoint（.pptx），以及純文字類（.txt .md .csv .json 等）。程式只改動文字內容，樣式、圖片、公式與版面都維持原樣。")
                Text("舊版 Office 檔（.doc／.xls／.ppt）").font(.headline)
                Text("舊版格式無法直接處理。請先在 Word／Excel／PowerPoint 或 LibreOffice 用「檔案 › 另存新檔」存成 .docx／.xlsx／.pptx，再交給本程式。PDF 無法原樣取代文字，不支援。")
                Text("隱私").font(.headline)
                Text("所有處理都在這台 Mac 上完成。模型伺服器只接受本機（127.0.0.1）連線，文件內容不會傳到網路；只有第一次載入模型時會連到模型下載來源（Rapid-MLX 鏡像或 Hugging Face）下載模型檔。原檔永遠不會被修改，輸出寫在原檔旁的新檔。")
                Text("限制").font(.headline)
                Text("模型可能漏抓姓名，尤其是較小的模型；請務必看過確認清單。只有姓氏加稱謂（例如「陳醫師」）不會被遮蔽。工作表名稱、圖表內的文字、圖片中的文字不會被處理。")
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
        }
    }
}
