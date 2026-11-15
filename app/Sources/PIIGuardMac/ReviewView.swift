import SwiftUI

struct ReviewView: View {
    @EnvironmentObject var state: AppState
    @Environment(\.dismiss) private var dismiss
    @State private var newName = ""

    var body: some View {
        if let job = state.review {
            content(job)
        } else {
            Text("目前沒有待確認的文件。").padding(40)
        }
    }

    private func typeLabel(_ t: String) -> String {
        ["person": "人名", "tw_id": "身分證", "phone": "電話", "email": "Email", "mrn": "病歷號"][t] ?? t
    }

    @ViewBuilder
    private func content(_ job: ReviewJob) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(job.file.lastPathComponent).font(.headline)
            Text("模型找到下列項目。取消勾選＝不遮蔽；漏掉的可在下方手動補上。原檔不會被更動。")
                .font(.callout).foregroundStyle(.secondary)

            HStack {
                Picker("遮蔽模式", selection: Binding(
                    get: { state.string("mode", "keep_surname") },
                    set: { state.set("mode", $0) })) {
                    ForEach(modeLabels(state.string("mask_char", "○")), id: \.0) { Text($0.1).tag($0.0) }
                }
                .frame(maxWidth: 380)
                Spacer()
                Text("共 \(job.entities.count) 項").foregroundStyle(.secondary)
            }

            List {
                ForEach(job.entities.indices, id: \.self) { i in
                    let e = job.entities[i]
                    HStack {
                        Toggle("", isOn: Binding(
                            get: { state.review?.entities[i].accepted ?? false },
                            set: { state.review?.entities[i].accepted = $0 }))
                            .labelsHidden()
                        Text(e.value).frame(minWidth: 110, alignment: .leading)
                        Image(systemName: "arrow.right").foregroundStyle(.tertiary)
                        Text(e.replacement).frame(minWidth: 110, alignment: .leading)
                            .foregroundStyle(e.accepted ? .primary : .tertiary)
                        Spacer()
                        Text(e.source == "manual" ? "手動" : typeLabel(e.type))
                            .font(.caption).foregroundStyle(.secondary)
                        Text("\(e.count) 處").font(.caption).monospacedDigit().foregroundStyle(.secondary)
                        Button("加入白名單") {
                            state.addToWhitelist(e.value)
                            state.review?.entities.remove(at: i)
                        }
                        .buttonStyle(.link).font(.caption)
                    }
                }
            }
            .frame(minHeight: 220)

            HStack {
                TextField("手動新增要遮蔽的文字（例如漏掉的姓名）", text: $newName)
                    .onSubmit(addManual)
                Button("新增", action: addManual).disabled(newName.trimmingCharacters(in: .whitespaces).isEmpty)
            }

            if !job.whitelisted.isEmpty {
                Text("已依白名單略過：\(job.whitelisted.joined(separator: "、"))")
                    .font(.caption).foregroundStyle(.secondary)
            }
            if job.discarded > 0 {
                Text("模型另回報 \(job.discarded) 個不在原文中或只有姓氏的字串，已自動捨棄。")
                    .font(.caption).foregroundStyle(.secondary)
            }

            HStack {
                Button("略過此檔") { state.skipCurrent(); dismiss() }
                Spacer()
                Button("寫出已勾選的項目") { finish(acceptAll: false) }
                Button("全部接受並寫出") { finish(acceptAll: true) }
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(16)
        .frame(minWidth: 600, minHeight: 480)
    }

    private func addManual() {
        let v = newName.trimmingCharacters(in: .whitespaces)
        guard !v.isEmpty, state.review?.entities.contains(where: { $0.value == v }) == false else { return }
        state.review?.entities.append(Entity(manual: v))
        newName = ""
        Task { await state.refreshPreview() }
    }

    private func finish(acceptAll: Bool) {
        guard let job = state.review else { return }
        dismiss()
        Task { await state.write(job, acceptAll: acceptAll) }
    }
}
