import SwiftUI

struct LoginView: View {

    @EnvironmentObject var authManager: AuthManager

    @State private var phone = ""
    @State private var code = ""
    @State private var isSendingCode = false
    @State private var isVerifying = false
    @State private var codeSent = false
    @State private var errorMessage = ""
    @State private var countdown = 0

    private let apiService = APIService()
    private let timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect()

    var body: some View {
        ZStack {
            // 渐变背景
            LinearGradient(
                colors: [Color(red: 0.05, green: 0.1, blue: 0.3), Color(red: 0.1, green: 0.2, blue: 0.5)],
                startPoint: .top,
                endPoint: .bottom
            )
            .ignoresSafeArea()

            // 装饰圆
            Circle()
                .fill(Color.blue.opacity(0.08))
                .frame(width: 340)
                .offset(x: 120, y: -280)
            Circle()
                .fill(Color.purple.opacity(0.06))
                .frame(width: 260)
                .offset(x: -100, y: -200)

            VStack(spacing: 0) {
                Spacer()

                // 顶部图标
                VStack(spacing: 16) {
                    Image(systemName: "shield.checkered")
                        .font(.system(size: 48))
                        .foregroundStyle(.white)
                        .shadow(color: .white.opacity(0.3), radius: 12)

                    Text("AI 消费者维权助手")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundColor(.white)

                    Text("保护你的每一笔消费权益")
                        .font(.subheadline)
                        .foregroundColor(.white.opacity(0.7))
                }

                Spacer().frame(height: 48)

                // 白色卡片
                VStack(spacing: 24) {
                    // 手机号
                    VStack(alignment: .leading, spacing: 8) {
                        Text("手机号")
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundColor(.secondary)

                        HStack(spacing: 12) {
                            HStack {
                                Image(systemName: "phone.fill")
                                    .font(.caption)
                                    .foregroundColor(.gray)
                                TextField("请输入手机号", text: $phone)
                                    .keyboardType(.numberPad)
                                    .disabled(codeSent)
                                    .onChange(of: phone) { _, newValue in
                                        if newValue.count > 11 { phone = String(newValue.prefix(11)) }
                                    }
                            }
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                            .background(Color(.systemGray6))
                            .clipShape(RoundedRectangle(cornerRadius: 12))

                            Button(action: sendCode) {
                                Group {
                                    if isSendingCode {
                                        ProgressView().tint(.white)
                                    } else if countdown > 0 {
                                        Text("\(countdown)s")
                                            .fontWeight(.semibold)
                                    } else {
                                        Text("获取验证码")
                                            .fontWeight(.semibold)
                                    }
                                }
                                .font(.subheadline)
                                .foregroundColor(.white)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 12)
                                .background(phone.count == 11 && !isSendingCode && countdown == 0
                                    ? AnyView(AppTheme.primaryGradient)
                                    : AnyView(Color.gray.opacity(0.3)))
                                .clipShape(RoundedRectangle(cornerRadius: 12))
                            }
                            .disabled(phone.count != 11 || isSendingCode || countdown > 0)
                        }
                    }

                    // 验证码
                    if codeSent {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("验证码")
                                .font(.caption)
                                .fontWeight(.medium)
                                .foregroundColor(.secondary)

                            HStack {
                                Image(systemName: "lock.shield.fill")
                                    .font(.caption)
                                    .foregroundColor(.gray)
                                TextField("请输入验证码", text: $code)
                                    .keyboardType(.numberPad)
                                    .onChange(of: code) { _, newValue in
                                        if newValue.count > 6 { code = String(newValue.prefix(6)) }
                                    }
                            }
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                            .background(Color(.systemGray6))
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                        .transition(.move(edge: .top).combined(with: .opacity))
                    }

                    // 错误
                    if !errorMessage.isEmpty {
                        HStack(spacing: 6) {
                            Image(systemName: "exclamationmark.circle.fill")
                                .font(.caption)
                            Text(errorMessage)
                                .font(.caption)
                        }
                        .foregroundColor(.red)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(Color.red.opacity(0.08))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    }

                    // 登录按钮
                    if codeSent {
                        Button(action: verifyCode) {
                            HStack(spacing: 8) {
                                if isVerifying {
                                    ProgressView().tint(.white)
                                }
                                Text("登录")
                                    .fontWeight(.semibold)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(code.count >= 4 ? AnyView(AppTheme.primaryGradient) : AnyView(Color.gray.opacity(0.3)))
                            .foregroundColor(.white)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                        .disabled(code.count < 4 || isVerifying)
                        .transition(.opacity)
                    }
                }
                .padding(24)
                .background(Color(.systemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 20))
                .shadow(color: .black.opacity(0.15), radius: 30, y: 10)
                .padding(.horizontal, 24)

                Spacer()

                // 提示
                HStack(spacing: 4) {
                    Image(systemName: "info.circle.fill")
                        .font(.caption2)
                    Text("演示版本，验证码固定为 123456")
                        .font(.caption2)
                }
                .foregroundColor(.white.opacity(0.6))
                .padding(.bottom, 40)
            }
        }
        .animation(.spring(response: 0.4, dampingFraction: 0.8), value: codeSent)
        .onReceive(timer) { _ in
            if countdown > 0 { countdown -= 1 }
        }
    }

    private func sendCode() {
        isSendingCode = true
        errorMessage = ""
        Task {
            do {
                _ = try await apiService.sendCode(phone: phone)
                await MainActor.run {
                    codeSent = true
                    countdown = 60
                    isSendingCode = false
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isSendingCode = false
                }
            }
        }
    }

    private func verifyCode() {
        isVerifying = true
        errorMessage = ""
        Task {
            do {
                let authData = try await apiService.verifyCode(phone: phone, code: code)
                await MainActor.run {
                    authManager.login(token: authData.token, phone: authData.phone)
                    isVerifying = false
                }
            } catch {
                await MainActor.run {
                    errorMessage = error.localizedDescription
                    isVerifying = false
                }
            }
        }
    }
}