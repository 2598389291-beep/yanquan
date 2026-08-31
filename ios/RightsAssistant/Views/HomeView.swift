import SwiftUI
import AVFoundation
import PhotosUI

struct HomeView: View {

    @EnvironmentObject var authManager: AuthManager

    @State private var appState: AppState = .idle
    @State private var complaint: ComplaintData?
    @State private var errorMessage: String = ""

    // 录音
    @State private var isRecording = false
    @State private var audioRecorder: AVAudioRecorder?
    @State private var recordingURL: URL?
    @State private var recordingAmplitude: CGFloat = 0.5

    // 图片上传
    @State private var selectedPhoto: PhotosPickerItem?
    @State private var previewImage: UIImage?
    @State private var isUploadingImage = false
    @State private var orderInfo: OrderInfo = .empty
    @State private var showOrderEditor = false

    // 文本输入
    @State private var textInput = ""

    private let apiService = APIService()

    var body: some View {
        NavigationStack {
            ZStack {
                Color(.systemGroupedBackground).ignoresSafeArea()

                ScrollView {
                    VStack(spacing: 20) {
                        // 状态栏
                        if authManager.isLoggedIn {
                            HStack {
                                Image(systemName: "person.circle.fill")
                                    .foregroundColor(.green)
                                Text("已登录：\(authManager.phone ?? "")")
                                    .font(.caption)
                                    .foregroundColor(.secondary)
                                Spacer()
                            }
                            .padding(.horizontal, 4)
                        }

                        switch appState {
                        case .idle:
                            idleContent
                        case .recording:
                            recordingContent
                        case .uploading, .generating:
                            PulseLoader(message: appState == .uploading ? "正在识别语音..." : "正在生成投诉信...")
                        case .result:
                            if let complaint = complaint {
                                resultContent(complaint)
                            }
                        case .error(let msg):
                            errorContent(msg)
                        }
                    }
                    .padding(.horizontal)
                    .padding(.top, 8)
                    .padding(.bottom, 24)
                }
                .scrollDismissesKeyboard(.immediately)
            }
            .navigationTitle("维权助手")
            .navigationBarTitleDisplayMode(.large)
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    HStack(spacing: 16) {
                        Button(action: { authManager.logout() }) {
                            Image(systemName: "rectangle.portrait.and.arrow.right")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }

                        NavigationLink(destination: HistoryView()) {
                            Image(systemName: "clock.arrow.circlepath")
                                .font(.subheadline)
                                .foregroundColor(.secondary)
                        }
                    }
                }
            }
        }
        .sheet(isPresented: $showOrderEditor) {
            OrderEditorView(orderInfo: $orderInfo)
        }
    }

    // MARK: - Idle

    private var idleContent: some View {
        VStack(spacing: 20) {
            // 顶部品牌
            VStack(spacing: 8) {
                Image(systemName: "shield.checkered")
                    .font(.system(size: 40))
                    .foregroundStyle(AppTheme.primaryGradient)

                Text("说出你的维权经历")
                    .font(.title3)
                    .fontWeight(.bold)

                Text("上传订单截图自动提取信息，AI 生成专业投诉信")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }
            .padding(.top, 8)

            // 图片上传
            imageUploadCard

            // 订单信息
            if hasOrderInfo() {
                orderInfoCard
            }

            // 录音按钮
            VStack(spacing: 16) {
                Button(action: {
                    HapticManager.impact(.medium)
                    startRecording()
                }) {
                    VStack(spacing: 14) {
                        ZStack {
                            Circle()
                                .fill(Color.blue.opacity(0.1))
                                .frame(width: 88, height: 88)
                            Circle()
                                .fill(AppTheme.primaryGradient)
                                .frame(width: 68, height: 68)
                                .shadow(color: .blue.opacity(0.3), radius: 12, y: 4)
                            Image(systemName: "mic.fill")
                                .font(.system(size: 30))
                                .foregroundColor(.white)
                        }
                        Text("点击开始录音")
                            .font(.headline)
                            .foregroundColor(.primary)
                        Text("说出你的维权经历，AI 自动生成投诉信")
                            .font(.caption)
                            .foregroundColor(.secondary)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 24)
                    .cardStyle()
                }
                .buttonStyle(.plain)
            }

            // 或
            HStack {
                line
                Text("或直接输入文字")
                    .font(.caption)
                    .foregroundColor(.secondary)
                    .padding(.horizontal, 8)
                line
            }

            // 文本输入
            textInputCard
        }
    }

    private var line: some View {
        Rectangle()
            .fill(Color.gray.opacity(0.2))
            .frame(height: 1)
    }

    // MARK: - 图片上传

    private var imageUploadCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "photo.on.rectangle.angled")
                    .foregroundColor(.blue)
                Text("上传订单截图（可选）")
                    .font(.headline)
            }

            PhotosPicker(selection: $selectedPhoto, matching: .images) {
                HStack(spacing: 16) {
                    // 图片预览
                    if let image = previewImage {
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFill()
                            .frame(width: 72, height: 72)
                            .clipShape(RoundedRectangle(cornerRadius: 10))
                    } else {
                        RoundedRectangle(cornerRadius: 10)
                            .fill(Color.blue.opacity(0.08))
                            .frame(width: 72, height: 72)
                            .overlay(
                                VStack(spacing: 4) {
                                    Image(systemName: "camera.fill")
                                        .font(.title3)
                                        .foregroundColor(.blue)
                                    Text("上传")
                                        .font(.caption2)
                                        .foregroundColor(.blue)
                                }
                            )
                    }

                    VStack(alignment: .leading, spacing: 4) {
                        Text("上传订单截图")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundColor(.primary)
                        Text("自动识别订单号、日期、金额等信息")
                            .font(.caption)
                            .foregroundColor(.secondary)

                        if isUploadingImage {
                            HStack(spacing: 6) {
                                ProgressView()
                                    .scaleEffect(0.6)
                                Text("正在识别...")
                                    .font(.caption2)
                                    .foregroundColor(.blue)
                            }
                        }
                    }

                    Spacer()

                    Image(systemName: "chevron.right")
                        .font(.caption)
                        .foregroundColor(.gray)
                }
            }

            if previewImage != nil {
                Button(action: {
                    withAnimation { clearImage() }
                }) {
                    HStack(spacing: 4) {
                        Image(systemName: "trash.fill")
                            .font(.caption2)
                        Text("清除图片")
                    }
                    .font(.caption)
                    .foregroundColor(.red)
                }
            }
        }
        .cardStyle()
        .onChange(of: selectedPhoto) { _, newItem in
            Task {
                if let data = try? await newItem?.loadTransferable(type: Data.self),
                   let image = UIImage(data: data) {
                    await MainActor.run {
                        withAnimation { previewImage = image }
                        isUploadingImage = true
                    }
                    do {
                        let info = try await apiService.uploadImage(data, fileName: "order.jpg", token: authManager.token)
                        await MainActor.run {
                            withAnimation { orderInfo = info }
                            isUploadingImage = false
                        }
                    } catch {
                        await MainActor.run {
                            isUploadingImage = false
                            errorMessage = "图片识别失败: \(error.localizedDescription)"
                        }
                    }
                }
            }
        }
    }

    private var orderInfoCard: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                Label("订单信息", systemImage: "doc.text.magnifyingglass")
                    .font(.headline)
                    .foregroundColor(.orange)
                Spacer()
                Button("编辑") { showOrderEditor = true }
                    .font(.caption)
                    .foregroundColor(.orange)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(Color.orange.opacity(0.1))
                    .clipShape(Capsule())
            }

            VStack(spacing: 6) {
                if !orderInfo.platform.isEmpty { infoRow(icon: "cart.fill", label: "平台", value: orderInfo.platform) }
                if !orderInfo.order_number.isEmpty { infoRow(icon: "number", label: "订单号", value: orderInfo.order_number) }
                if !orderInfo.order_date.isEmpty { infoRow(icon: "calendar", label: "日期", value: orderInfo.order_date) }
                if !orderInfo.product_name.isEmpty { infoRow(icon: "shippingbox", label: "商品", value: orderInfo.product_name) }
                if !orderInfo.amount.isEmpty { infoRow(icon: "yensign", label: "金额", value: "\(orderInfo.amount) 元") }
                if !orderInfo.seller.isEmpty { infoRow(icon: "storefront", label: "商家", value: orderInfo.seller) }
            }
        }
        .cardStyleAccent(.orange)
        .transition(.move(edge: .top).combined(with: .opacity))
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

    // MARK: - 文本输入

    private var textInputCard: some View {
        VStack(spacing: 12) {
            ZStack(alignment: .topLeading) {
                if textInput.isEmpty {
                    Text("例如：我在拼多多买了一个手机，花了2000块，用了三天就坏了...")
                        .foregroundColor(.gray.opacity(0.5))
                        .padding(.horizontal, 14)
                        .padding(.vertical, 12)
                }
                TextEditor(text: $textInput)
                    .frame(height: 88)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 8)
                    .scrollContentBackground(.hidden)
                    .background(Color(.systemGray6))
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }

            Button(action: submitText) {
                HStack(spacing: 6) {
                    Image(systemName: "paperplane.fill")
                        .font(.subheadline)
                    Text("生成投诉信")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
                .background(textInput.trimmed.isEmpty ? AnyView(Color.gray.opacity(0.2)) : AnyView(AppTheme.primaryGradient))
                .foregroundColor(textInput.trimmed.isEmpty ? .secondary : .white)
                .clipShape(RoundedRectangle(cornerRadius: 12))
            }
            .disabled(textInput.trimmed.isEmpty)
        }
        .cardStyle()
    }

    // MARK: - 录音

    private var recordingContent: some View {
        VStack(spacing: 32) {
            // 波形动画
            ZStack {
                ForEach(0..<4) { i in
                    Circle()
                        .stroke(Color.red.opacity(0.15 - Double(i) * 0.03), lineWidth: 2)
                        .frame(width: CGFloat(120 + i * 28))
                        .scaleEffect(isRecording ? 1.0 + CGFloat(i) * 0.08 : 1.0)
                        .opacity(isRecording ? 0.8 - Double(i) * 0.15 : 0.3)
                        .animation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true).delay(Double(i) * 0.15), value: isRecording)
                }

                Circle()
                    .fill(Color.red.opacity(0.1))
                    .frame(width: 100, height: 100)

                Circle()
                    .fill(Color.red)
                    .frame(width: 72, height: 72)
                    .shadow(color: .red.opacity(0.4), radius: 16, y: 4)

                Image(systemName: "mic.fill")
                    .font(.system(size: 32))
                    .foregroundColor(.white)
            }

            VStack(spacing: 6) {
                Text("正在录音...")
                    .font(.title3)
                    .fontWeight(.bold)

                Text("请清晰说出你的维权经历\n说完了点击下方按钮停止")
                    .font(.subheadline)
                    .foregroundColor(.secondary)
                    .multilineTextAlignment(.center)
            }

            // 提示
            HStack(spacing: 6) {
                Image(systemName: "lightbulb.fill")
                    .font(.caption2)
                Text("建议包含：平台、商品、金额、时间、问题描述")
                    .font(.caption)
            }
            .foregroundColor(.orange)
            .padding(.horizontal, 14)
            .padding(.vertical, 8)
            .background(Color.orange.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: 8))

            Button(action: stopRecording) {
                HStack(spacing: 8) {
                    Image(systemName: "stop.fill")
                    Text("停止录音")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 14)
                .background(Color.red)
                .foregroundColor(.white)
                .clipShape(RoundedRectangle(cornerRadius: 14))
                .shadow(color: .red.opacity(0.3), radius: 8, y: 4)
            }
            .padding(.horizontal, 20)
        }
        .padding(.vertical, 40)
        .cardStyle()
        .onAppear { isRecording = true }
    }

    // MARK: - 结果

    private func resultContent(_ complaint: ComplaintData) -> some View {
        VStack(alignment: .leading, spacing: 16) {
            // 顶部信息条
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
            if let oi = complaint.order_info, hasOrderInfoFrom(oi) {
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

            // 操作按钮
            VStack(spacing: 12) {
                Button(action: {
                    UIPasteboard.general.string = complaint.complaint_letter
                    HapticManager.notification(.success)
                }) {
                    HStack(spacing: 8) {
                        Image(systemName: "doc.on.doc.fill")
                        Text("复制投诉信")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(AppTheme.primaryGradient)
                    .foregroundColor(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                    .shadow(color: .blue.opacity(0.3), radius: 8, y: 4)
                }

                Button(action: { withAnimation { resetState() } }) {
                    HStack(spacing: 6) {
                        Image(systemName: "arrow.counterclockwise")
                        Text("再来一次")
                    }
                    .fontWeight(.medium)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(Color(.systemGray6))
                    .foregroundColor(.primary)
                    .clipShape(RoundedRectangle(cornerRadius: 14))
                }
            }
            .padding(.top, 4)
        }
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

    private func hasOrderInfoFrom(_ oi: OrderInfo) -> Bool {
        !oi.order_number.isEmpty || !oi.platform.isEmpty || !oi.amount.isEmpty
    }

    private func hasOrderInfo() -> Bool {
        !orderInfo.order_number.isEmpty || !orderInfo.platform.isEmpty || !orderInfo.amount.isEmpty
    }

    private func clearImage() {
        previewImage = nil
        selectedPhoto = nil
        orderInfo = .empty
    }

    // MARK: - 错误

    private func errorContent(_ message: String) -> some View {
        VStack(spacing: 20) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 48))
                .foregroundColor(.orange)

            Text(message)
                .font(.headline)
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)

            Button(action: { withAnimation { resetState() } }) {
                Text("重试")
                    .fontWeight(.semibold)
                    .padding(.horizontal, 32)
                    .padding(.vertical, 12)
                    .background(Color.blue)
                    .foregroundColor(.white)
                    .clipShape(RoundedRectangle(cornerRadius: 12))
            }
        }
        .cardStyle()
        .padding(.vertical, 20)
    }

    // MARK: - 录音逻辑

    private func startRecording() {
        let session = AVAudioSession.sharedInstance()
        do {
            try session.setCategory(.playAndRecord, mode: .default)
            try session.setActive(true)
        } catch {
            appState = .error("麦克风权限未开启，请在设置中允许")
            return
        }

        let tempDir = FileManager.default.temporaryDirectory
        recordingURL = tempDir.appendingPathComponent("\(UUID().uuidString).m4a")

        let settings: [String: Any] = [
            AVFormatIDKey: Int(kAudioFormatMPEG4AAC),
            AVSampleRateKey: 16000,
            AVNumberOfChannelsKey: 1,
            AVEncoderAudioQualityKey: AVAudioQuality.high.rawValue,
        ]

        do {
            audioRecorder = try AVAudioRecorder(url: recordingURL!, settings: settings)
            audioRecorder?.record()
            appState = .recording
        } catch {
            appState = .error("录音初始化失败: \(error.localizedDescription)")
        }
    }

    private func stopRecording() {
        audioRecorder?.stop()
        isRecording = false
        appState = .uploading

        guard let url = recordingURL, let audioData = try? Data(contentsOf: url) else {
            appState = .error("录音文件读取失败")
            return
        }

        let oi = hasOrderInfo() ? orderInfo : nil

        Task {
            do {
                let result = try await apiService.uploadVoice(
                    audioData: audioData,
                    fileName: "recording.m4a",
                    orderInfo: oi,
                    token: authManager.token
                )
                await MainActor.run {
                    withAnimation { complaint = result; appState = .result }
                }
            } catch {
                await MainActor.run {
                    appState = .error(error.localizedDescription)
                }
            }
        }
    }

    private func submitText() {
        let text = textInput.trimmed
        guard !text.isEmpty else { return }

        appState = .generating
        let oi = hasOrderInfo() ? orderInfo : nil

        Task {
            do {
                let result = try await apiService.submitText(text, orderInfo: oi, token: authManager.token)
                await MainActor.run {
                    withAnimation { complaint = result; textInput = ""; appState = .result }
                }
            } catch {
                await MainActor.run {
                    appState = .error(error.localizedDescription)
                }
            }
        }
    }

    private func resetState() {
        complaint = nil
        textInput = ""
        orderInfo = .empty
        previewImage = nil
        selectedPhoto = nil
        appState = .idle
    }
}

// MARK: - 订单信息编辑器

struct OrderEditorView: View {
    @Binding var orderInfo: OrderInfo
    @Environment(\.dismiss) var dismiss

    var body: some View {
        NavigationStack {
            List {
                Section("平台") {
                    TextField("如：拼多多、淘宝、京东", text: $orderInfo.platform)
                }
                Section("订单号") {
                    TextField("订单号/交易单号", text: $orderInfo.order_number)
                }
                Section("日期") {
                    TextField("如：2024-01-15", text: $orderInfo.order_date)
                }
                Section("商品名称") {
                    TextField("商品名称", text: $orderInfo.product_name)
                }
                Section("金额") {
                    TextField("如：2000.00", text: $orderInfo.amount)
                        .keyboardType(.decimalPad)
                }
                Section("商家") {
                    TextField("商家/店铺名称", text: $orderInfo.seller)
                }
            }
            .navigationTitle("编辑订单信息")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) {
                    Button("完成") { dismiss() }
                        .fontWeight(.semibold)
                }
            }
        }
    }
}

// MARK: - 字符串扩展

extension String {
    var trimmed: String {
        trimmingCharacters(in: .whitespacesAndNewlines)
    }
}