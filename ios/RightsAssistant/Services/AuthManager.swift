import Foundation

/// 用户认证状态管理器（Token 持久化）
class AuthManager: ObservableObject {

    @Published var authState: AuthState = .unauthenticated

    private let tokenKey = "auth_token"
    private let phoneKey = "auth_phone"

    init() {
        loadFromStorage()
    }

    var token: String? {
        if case .authenticated(let token, _) = authState { return token }
        return nil
    }

    var phone: String? {
        if case .authenticated(_, let phone) = authState { return phone }
        return nil
    }

    var isLoggedIn: Bool {
        if case .authenticated = authState { return true }
        return false
    }

    func login(token: String, phone: String) {
        UserDefaults.standard.set(token, forKey: tokenKey)
        UserDefaults.standard.set(phone, forKey: phoneKey)
        authState = .authenticated(token: token, phone: phone)
    }

    func logout() {
        UserDefaults.standard.removeObject(forKey: tokenKey)
        UserDefaults.standard.removeObject(forKey: phoneKey)
        authState = .unauthenticated
    }

    private func loadFromStorage() {
        if let token = UserDefaults.standard.string(forKey: tokenKey),
           let phone = UserDefaults.standard.string(forKey: phoneKey),
           !token.isEmpty {
            authState = .authenticated(token: token, phone: phone)
        }
    }
}