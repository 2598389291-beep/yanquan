import SwiftUI

// MARK: - 主题色
struct AppTheme {
    static let primary = Color.blue
    static let primaryGradient = LinearGradient(
        colors: [Color(red: 0.2, green: 0.4, blue: 1.0), Color(red: 0.0, green: 0.2, blue: 0.8)],
        startPoint: .topLeading,
        endPoint: .bottomTrailing
    )
    static let accentGradient = LinearGradient(
        colors: [Color(red: 0.4, green: 0.2, blue: 1.0), Color(red: 0.0, green: 0.4, blue: 0.8)],
        startPoint: .leading,
        endPoint: .trailing
    )
    static let cardBackground = Color(.systemGray6)
    static let cardShadow = Color.black.opacity(0.08)
}

// MARK: - 卡片样式
struct CardStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding()
            .background(Color(.systemBackground))
            .clipShape(RoundedRectangle(cornerRadius: 16))
            .shadow(color: AppTheme.cardShadow, radius: 8, y: 4)
    }
}

struct CardStyleAccent: ViewModifier {
    let color: Color
    func body(content: Content) -> some View {
        content
            .padding()
            .background(color.opacity(0.06))
            .overlay(
                RoundedRectangle(cornerRadius: 16)
                    .stroke(color.opacity(0.15), lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}

extension View {
    func cardStyle() -> some View {
        modifier(CardStyle())
    }
    func cardStyleAccent(_ color: Color) -> some View {
        modifier(CardStyleAccent(color: color))
    }
}

// MARK: - 触觉反馈
struct HapticManager {
    static func impact(_ style: UIImpactFeedbackGenerator.FeedbackStyle) {
        UIImpactFeedbackGenerator(style: style).impactOccurred()
    }
    static func notification(_ type: UINotificationFeedbackGenerator.FeedbackType) {
        UINotificationFeedbackGenerator().notificationOccurred(type)
    }
}

// MARK: - 加载动画
struct PulseLoader: View {
    @State private var scale: CGFloat = 1.0
    let message: String

    var body: some View {
        VStack(spacing: 24) {
            Circle()
                .stroke(AppTheme.primaryGradient, lineWidth: 3)
                .frame(width: 48, height: 48)
                .scaleEffect(scale)
                .animation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true), value: scale)
                .onAppear { scale = 1.3 }

            Text(message)
                .font(.headline)
                .foregroundColor(.secondary)
        }
        .padding(.vertical, 60)
    }
}