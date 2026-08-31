import SwiftUI

struct HistoryView: View {

    @EnvironmentObject var authManager: AuthManager

    @State private var items: [ComplaintListItem] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    private let apiService = APIService()

    var body: some View {
        ZStack {
            Color(.systemGroupedBackground).ignoresSafeArea()

            Group {
                if isLoading {
                    PulseLoader(message: "加载中...")
                } else if let error = errorMessage {
                    VStack(spacing: 16) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.system(size: 48))
                            .foregroundColor(.orange)
                        Text(error)
                            .font(.headline)
                            .foregroundColor(.secondary)
                            .multilineTextAlignment(.center)
                        Button(action: loadHistory) {
                            Text("重试")
                                .fontWeight(.semibold)
                                .padding(.horizontal, 32)
                                .padding(.vertical, 12)
                                .background(Color.blue)
                                .foregroundColor(.white)
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                    }
                    .padding()
                } else if items.isEmpty {
                    VStack(spacing: 16) {
                        Image(systemName: "clock.badge.questionmark")
                            .font(.system(size: 56))
                            .foregroundColor(.gray.opacity(0.5))
                        Text("暂无维权记录")
                            .font(.headline)
                            .foregroundColor(.secondary)
                        Text("录音或输入文字生成投诉信后\n记录将出现在这里")
                            .font(.subheadline)
                            .foregroundColor(.gray)
                            .multilineTextAlignment(.center)
                    }
                } else {
                    ScrollView {
                        LazyVStack(spacing: 12) {
                            ForEach(items) { item in
                                NavigationLink(destination: ComplaintDetailView(complaintId: item.id)) {
                                    historyCard(item)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding()
                    }
                }
            }
        }
        .navigationTitle("维权记录")
        .navigationBarTitleDisplayMode(.large)
        .onAppear { loadHistory() }
    }

    private func historyCard(_ item: ComplaintListItem) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                categoryBadge(item.category)
                Spacer()
                Text(item.created_at)
                    .font(.caption2)
                    .foregroundColor(.secondary)
            }

            Text(item.raw_text)
                .font(.subheadline)
                .lineLimit(2)
                .lineSpacing(4)
                .foregroundColor(.primary)

            HStack {
                Spacer()
                HStack(spacing: 4) {
                    Text("查看详情")
                        .font(.caption)
                        .foregroundColor(.blue)
                    Image(systemName: "chevron.right")
                        .font(.caption2)
                        .foregroundColor(.blue)
                }
            }
        }
        .padding()
        .background(Color(.systemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .shadow(color: .black.opacity(0.05), radius: 6, y: 3)
    }

    private func categoryBadge(_ text: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: "tag.fill")
                .font(.caption2)
            Text(text)
                .font(.caption)
                .fontWeight(.semibold)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(Color.blue.opacity(0.1))
        .foregroundColor(.blue)
        .clipShape(Capsule())
    }

    private func loadHistory() {
        isLoading = true
        errorMessage = nil
        Task {
            do {
                let result = try await apiService.fetchHistory(token: authManager.token)
                await MainActor.run {
                    items = result.items
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }
}

// MARK: - 投诉详情页

struct ComplaintDetailView: View {

    let complaintId: Int
    @State private var complaint: ComplaintData?
    @State private var isLoading = true
    @State private var errorMessage: String?

    private let apiService = APIService()

    var body: some View {
        ZStack {
            Color(.systemGroupedBackground).ignoresSafeArea()

            ScrollView {
                if isLoading {
                    PulseLoader(message: "加载中...")
                        .padding(.top, 40)
                } else if let error = errorMessage {
                    VStack(spacing: 12) {
                        Image(systemName: "exclamationmark.triangle")
                            .font(.largeTitle)
                            .foregroundColor(.orange)
                        Text(error)
                            .foregroundColor(.secondary)
                    }
                    .padding(.top, 40)
                } else if let complaint = complaint {
                    VStack(alignment: .leading, spacing: 16) {
                        // 顶部信息
                        HStack {
                            Label(complaint.created_at, systemImage: "clock")
                                .font(.caption)
                                .foregroundColor(.secondary)
                            Spacer()
                            Text("单号 #\(complaint.id)")
                                .font(.caption)
                                .fontWeight(.semibold)
                                .foregroundColor(.secondary)
                                .padding(.horizontal, 10)
                                .padding(.vertical, 4)
                                .background(Color(.systemGray6))
                                .clipShape(Capsule())
                        }

                        // 类别
                        HStack {
                            categoryBadge(complaint.category)
                            Spacer()
                        }

                        // 订单信息
                        if let oi = complaint.order_info,
                           !oi.order_number.isEmpty || !oi.platform.isEmpty || !oi.amount.isEmpty {
                            VStack(alignment: .leading, spacing: 10) {
                                Label("订单信息", systemImage: "doc.text.magnifyingglass")
                                    .font(.headline)
                                    .foregroundColor(.orange)
                                VStack(spacing: 5) {
                                    if !oi.platform.isEmpty { infoRow(icon: "cart.fill", label: "平台", value: oi.platform) }
                                    if !oi.order_number.isEmpty { infoRow(icon: "number", label: "订单号", value: oi.order_number) }
                                    if !oi.order_date.isEmpty { infoRow(icon: "calendar", label: "日期", value: oi.order_date) }
                                    if !oi.amount.isEmpty { infoRow(icon: "yensign", label: "金额", value: "\(oi.amount) 元") }
                                }
                            }
                            .cardStyleAccent(.orange)
                        }

                        // 你说的内容
                        VStack(alignment: .leading, spacing: 8) {
                            Label("你说的内容", systemImage: "waveform")
                                .font(.headline)
                                .foregroundColor(.purple)
                            Text(complaint.raw_text)
                                .font(.subheadline)
                                .lineSpacing(5)
                                .foregroundColor(.primary)
                        }
                        .cardStyleAccent(.purple)

                        // 投诉信
                        VStack(alignment: .leading, spacing: 8) {
                            Label("投诉信", systemImage: "doc.text.fill")
                                .font(.headline)
                                .foregroundColor(.blue)
                            Text(complaint.complaint_letter)
                                .font(.subheadline)
                                .lineSpacing(6)
                                .foregroundColor(.primary)
                        }
                        .cardStyleAccent(.blue)

                        // 法律依据
                        VStack(alignment: .leading, spacing: 8) {
                            Label("引用法律依据", systemImage: "book.fill")
                                .font(.headline)
                                .foregroundColor(.orange)
                            ForEach(complaint.legal_basis, id: \.self) { law in
                                HStack(alignment: .top, spacing: 8) {
                                    Image(systemName: "checkmark.circle.fill")
                                        .font(.caption)
                                        .foregroundColor(.orange)
                                    Text(law)
                                        .font(.subheadline)
                                        .foregroundColor(.secondary)
                                }
                            }
                        }
                        .cardStyleAccent(.orange)

                        // 维权路径
                        VStack(alignment: .leading, spacing: 8) {
                            Label("维权路径", systemImage: "map.fill")
                                .font(.headline)
                                .foregroundColor(.green)
                            ForEach(complaint.action_path) { step in
                                HStack(alignment: .top, spacing: 14) {
                                    ZStack {
                                        Circle()
                                            .fill(Color.green)
                                            .frame(width: 28, height: 28)
                                        Text("\(step.step)")
                                            .font(.caption)
                                            .fontWeight(.bold)
                                            .foregroundColor(.white)
                                    }
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(step.action)
                                            .font(.subheadline)
                                            .fontWeight(.semibold)
                                            .foregroundColor(.primary)
                                        Text(step.detail)
                                            .font(.caption)
                                            .foregroundColor(.secondary)
                                            .lineSpacing(3)
                                    }
                                }
                            }
                        }
                        .cardStyleAccent(.green)
                    }
                    .padding()
                }
            }
        }
        .navigationTitle("投诉详情")
        .navigationBarTitleDisplayMode(.inline)
        .onAppear { loadDetail() }
    }

    private func categoryBadge(_ text: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: "tag.fill")
                .font(.caption2)
            Text(text)
                .font(.caption)
                .fontWeight(.semibold)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 6)
        .background(Color.blue.opacity(0.1))
        .foregroundColor(.blue)
        .clipShape(Capsule())
    }

    private func infoRow(icon: String, label: String, value: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .font(.caption2)
                .foregroundColor(.orange)
                .frame(width: 16)
            Text(label)
                .font(.caption)
                .foregroundColor(.secondary)
                .frame(width: 40, alignment: .leading)
            Text(value)
                .font(.subheadline)
                .fontWeight(.medium)
            Spacer()
        }
    }

    private func loadDetail() {
        Task {
            do {
                let result = try await apiService.fetchComplaint(id: complaintId)
                await MainActor.run {
                    complaint = result
                    isLoading = false
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isLoading = false
                }
            }
        }
    }
}