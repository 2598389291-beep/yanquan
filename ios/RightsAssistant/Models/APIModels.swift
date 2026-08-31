import Foundation

// MARK: - API 请求模型

struct TextComplaintRequest: Codable {
    let text: String
    let user_id: String
    let order_info: OrderInfo?
}

struct SendCodeRequest: Codable {
    let phone: String
}

struct VerifyCodeRequest: Codable {
    let phone: String
    let code: String
}

// MARK: - API 响应模型

struct APIResponse<T: Codable>: Codable {
    let code: Int
    let data: T?
    let detail: String?
}

struct ComplaintData: Codable, Identifiable {
    let id: Int
    let raw_text: String
    let complaint_letter: String
    let legal_basis: [String]
    let action_path: [ActionStep]
    let category: String
    let order_info: OrderInfo?
    let created_at: String
}

struct ActionStep: Codable, Identifiable {
    let step: Int
    let action: String
    let detail: String

    var id: Int { step }
}

struct ComplaintListItem: Codable, Identifiable {
    let id: Int
    let category: String
    let raw_text: String
    let created_at: String
}

struct ComplaintListData: Codable {
    let items: [ComplaintListItem]
    let total: Int
    let page: Int
    let page_size: Int
}

// MARK: - 订单信息（OCR 识别结果）

struct OrderInfo: Codable {
    var platform: String
    var order_number: String
    var order_date: String
    var product_name: String
    var amount: String
    var seller: String

    static let empty = OrderInfo(
        platform: "",
        order_number: "",
        order_date: "",
        product_name: "",
        amount: "",
        seller: ""
    )
}

// MARK: - 认证

struct AuthData: Codable {
    let token: String
    let phone: String
    let user_id: Int
    let expires_at: String
}

struct SendCodeData: Codable {
    let phone: String
    let message: String
}

// MARK: - App 状态

enum AppState: Equatable {
    case idle
    case recording
    case uploading
    case generating
    case result
    case error(String)

    static func == (lhs: AppState, rhs: AppState) -> Bool {
        switch (lhs, rhs) {
        case (.idle, .idle), (.recording, .recording), (.uploading, .uploading), (.generating, .generating), (.result, .result):
            return true
        case (.error, .error):
            return true
        default:
            return false
        }
    }
}

enum AuthState {
    case unauthenticated
    case authenticated(token: String, phone: String)
}