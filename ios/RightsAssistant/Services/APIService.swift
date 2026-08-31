import Foundation

/// 后端 API 服务
class APIService {

    static let baseURL = "http://192.168.31.158:8000"

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder

    init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 60
        config.timeoutIntervalForResource = 120
        self.session = URLSession(configuration: config)
        self.decoder = JSONDecoder()
        self.encoder = JSONEncoder()
    }

    // MARK: - 认证

    func sendCode(phone: String) async throws -> String {
        let url = URL(string: "\(Self.baseURL)/api/auth/send-code")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(SendCodeRequest(phone: phone))

        let (data, response) = try await session.data(for: request)
        try checkResponse(response, data)
        let resp = try decoder.decode(APIResponse<SendCodeData>.self, from: data)
        return resp.data?.message ?? "验证码已发送"
    }

    func verifyCode(phone: String, code: String) async throws -> AuthData {
        let url = URL(string: "\(Self.baseURL)/api/auth/verify")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(VerifyCodeRequest(phone: phone, code: code))

        let (data, response) = try await session.data(for: request)
        try checkResponse(response, data)
        let resp = try decoder.decode(APIResponse<AuthData>.self, from: data)
        guard let authData = resp.data else { throw APIError.noData }
        return authData
    }

    // MARK: - OCR 图片识别

    func uploadImage(_ imageData: Data, fileName: String, token: String?) async throws -> OrderInfo {
        let url = URL(string: "\(Self.baseURL)/api/ocr/extract")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        if let token = token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        var body = Data()
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"user_id\"\r\n\r\n".data(using: .utf8)!)
        body.append("ios_user\r\n".data(using: .utf8)!)

        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: image/\(fileName.hasSuffix("png") ? "png" : "jpeg")\r\n\r\n".data(using: .utf8)!)
        body.append(imageData)
        body.append("\r\n".data(using: .utf8)!)
        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body

        let (data, response) = try await session.data(for: request)
        try checkResponse(response, data)
        let resp = try decoder.decode(APIResponse<OrderInfo>.self, from: data)
        guard let orderInfo = resp.data else { throw APIError.noData }
        return orderInfo
    }

    // MARK: - 文本投诉

    func submitText(_ text: String, userId: String = "ios_user", orderInfo: OrderInfo? = nil, token: String? = nil) async throws -> ComplaintData {
        let url = URL(string: "\(Self.baseURL)/api/complaint/text")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        if let token = token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let body = TextComplaintRequest(text: text, user_id: userId, order_info: orderInfo)
        request.httpBody = try encoder.encode(body)

        let (data, response) = try await session.data(for: request)
        try checkResponse(response, data)
        let apiResponse = try decoder.decode(APIResponse<ComplaintData>.self, from: data)
        guard let complaintData = apiResponse.data else { throw APIError.noData }
        return complaintData
    }

    // MARK: - 语音投诉

    func uploadVoice(audioData: Data, fileName: String, userId: String = "ios_user", orderInfo: OrderInfo? = nil, token: String? = nil) async throws -> ComplaintData {
        let url = URL(string: "\(Self.baseURL)/api/complaint/voice")!
        var request = URLRequest(url: url)
        request.httpMethod = "POST"

        let boundary = UUID().uuidString
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        if let token = token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        var body = Data()

        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"user_id\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(userId)\r\n".data(using: .utf8)!)

        // order_info
        let orderInfoJSON = (try? encoder.encode(orderInfo ?? OrderInfo.empty)).flatMap { String(data: $0, encoding: .utf8) } ?? "{}"
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"order_info\"\r\n\r\n".data(using: .utf8)!)
        body.append("\(orderInfoJSON)\r\n".data(using: .utf8)!)

        // file
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"file\"; filename=\"\(fileName)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: audio/m4a\r\n\r\n".data(using: .utf8)!)
        body.append(audioData)
        body.append("\r\n".data(using: .utf8)!)

        body.append("--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body

        let (data, response) = try await session.data(for: request)
        try checkResponse(response, data)
        let apiResponse = try decoder.decode(APIResponse<ComplaintData>.self, from: data)
        guard let complaintData = apiResponse.data else { throw APIError.noData }
        return complaintData
    }

    // MARK: - 获取历史记录

    func fetchHistory(userId: String = "ios_user", page: Int = 1, token: String? = nil) async throws -> ComplaintListData {
        let url = URL(string: "\(Self.baseURL)/api/complaints?user_id=\(userId)&page=\(page)")!
        var request = URLRequest(url: url)
        if let token = token {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        let (data, response) = try await session.data(for: request)
        try checkResponse(response, data)
        let apiResponse = try decoder.decode(APIResponse<ComplaintListData>.self, from: data)
        guard let listData = apiResponse.data else { throw APIError.noData }
        return listData
    }

    // MARK: - 获取单条详情

    func fetchComplaint(id: Int) async throws -> ComplaintData {
        let url = URL(string: "\(Self.baseURL)/api/complaint/\(id)")!
        let (data, response) = try await session.data(from: url)
        try checkResponse(response, data)
        let apiResponse = try decoder.decode(APIResponse<ComplaintData>.self, from: data)
        guard let complaintData = apiResponse.data else { throw APIError.noData }
        return complaintData
    }

    // MARK: - 辅助

    private func checkResponse(_ response: URLResponse, _ data: Data) throws {
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        if httpResponse.statusCode != 200 {
            let errorResp = try? decoder.decode(APIResponse<ComplaintData>.self, from: data)
            let detail = errorResp?.detail ?? "服务器错误"
            throw APIError.serverError(detail)
        }
    }
}

// MARK: - 错误类型

enum APIError: LocalizedError {
    case invalidResponse
    case badRequest(String)
    case serverError(String)
    case noData

    var errorDescription: String? {
        switch self {
        case .invalidResponse:
            return "服务器响应异常"
        case .badRequest(let msg):
            return msg
        case .serverError(let msg):
            return msg
        case .noData:
            return "未获取到数据"
        }
    }
}