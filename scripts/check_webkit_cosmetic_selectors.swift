#!/usr/bin/env swift

import Foundation
import WebKit

struct CosmeticRule: Decodable {
    let id: String
    let selector: String
    let domains: [String]
}

struct MergedFilterFile: Decodable {
    let webBlockFilterVersion: String
    let cosmeticRules: [CosmeticRule]

    enum CodingKeys: String, CodingKey {
        case webBlockFilterVersion = "web-block-filter-version"
        case cosmeticRules = "cosmetic-rules"
    }
}

struct SelectorOccurrence: Encodable {
    let id: String
    let domains: [String]
}

struct InvalidSelectorReport: Encodable {
    let selector: String
    let error: String
    let occurrences: [SelectorOccurrence]
}

struct ProgramOptions {
    let inputPath: String
    let outputPath: String?
    let batchSize: Int
}

final class NavigationDelegate: NSObject, WKNavigationDelegate {
    var onFinish: (() -> Void)?

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        onFinish?()
    }
}

final class SelectorValidator {
    let webView: WKWebView
    private let navigationDelegate: NavigationDelegate

    init() {
        webView = WKWebView(frame: .zero)
        navigationDelegate = NavigationDelegate()
        var didFinishLoad = false

        navigationDelegate.onFinish = {
            didFinishLoad = true
        }
        webView.navigationDelegate = navigationDelegate

        let html = "<!doctype html><html><head><meta charset=\"utf-8\"></head><body></body></html>"
        webView.loadHTMLString(html, baseURL: nil)
        waitUntil(didFinishLoad)
    }
}

func parseArgs() -> ProgramOptions {
    var inputPath = "dist/easylist.json"
    var outputPath: String?
    var batchSize = 512

    var index = 1
    let arguments = CommandLine.arguments
    while index < arguments.count {
        let argument = arguments[index]
        switch argument {
        case "--input":
            index += 1
            inputPath = arguments[index]
        case "--output":
            index += 1
            outputPath = arguments[index]
        case "--batch-size":
            index += 1
            batchSize = Int(arguments[index]) ?? batchSize
        default:
            fputs("unknown argument: \(argument)\n", stderr)
            exit(2)
        }
        index += 1
    }

    if batchSize <= 0 {
        fputs("--batch-size must be greater than zero\n", stderr)
        exit(2)
    }

    return ProgramOptions(
        inputPath: inputPath,
        outputPath: outputPath,
        batchSize: batchSize
    )
}

func waitUntil(_ condition: @autoclosure () -> Bool) {
    while !condition() {
        RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.01))
    }
}

func makeValidationScript(selectors: [String]) throws -> String {
    let payload = try JSONSerialization.data(withJSONObject: selectors, options: [])
    guard let selectorJSON = String(data: payload, encoding: .utf8) else {
        throw NSError(
            domain: "SelectorCheck",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "failed to encode selector batch"]
        )
    }

    return """
    (() => {
      const selectors = \(selectorJSON);
      const invalid = [];
      for (const selector of selectors) {
        try {
          document.querySelectorAll(selector);
        } catch (error) {
          invalid.push({
            selector,
            error: String(error),
          });
        }
      }
      return JSON.stringify(invalid);
    })();
    """
}

func validateSelectors(
    in validator: SelectorValidator,
    selectors: [String]
) throws -> [String: String] {
    let script = try makeValidationScript(selectors: selectors)
    let semaphore = DispatchSemaphore(value: 0)
    var evaluationResult: Result<[String: String], Error>?

    validator.webView.evaluateJavaScript(script) { result, error in
        defer {
            semaphore.signal()
        }

        if let error {
            evaluationResult = .failure(error)
            return
        }

        guard let text = result as? String else {
            evaluationResult = .failure(
                NSError(
                    domain: "SelectorCheck",
                    code: 2,
                    userInfo: [NSLocalizedDescriptionKey: "unexpected JavaScript result"]
                )
            )
            return
        }

        do {
            let data = Data(text.utf8)
            let entries = try JSONSerialization.jsonObject(with: data) as? [[String: String]] ?? []
            var invalidSelectors: [String: String] = [:]
            for entry in entries {
                if let selector = entry["selector"], let error = entry["error"] {
                    invalidSelectors[selector] = error
                }
            }
            evaluationResult = .success(invalidSelectors)
        } catch {
            evaluationResult = .failure(error)
        }
    }

    waitUntil(semaphore.wait(timeout: .now()) == .success)
    return try evaluationResult!.get()
}

let options = parseArgs()
let inputURL = URL(fileURLWithPath: options.inputPath)

let data = try Data(contentsOf: inputURL)
let decoder = JSONDecoder()
let rules = try decoder.decode(MergedFilterFile.self, from: data).cosmeticRules

var selectorOccurrences: [String: [SelectorOccurrence]] = [:]
for rule in rules {
    selectorOccurrences[rule.selector, default: []].append(
        SelectorOccurrence(id: rule.id, domains: rule.domains)
    )
}

let selectors = Array(selectorOccurrences.keys).sorted()
let validator = SelectorValidator()
var invalidSelectors: [String: String] = [:]

var start = 0
while start < selectors.count {
    let end = min(start + options.batchSize, selectors.count)
    let batch = Array(selectors[start..<end])
    let invalidBatch = try validateSelectors(in: validator, selectors: batch)
    invalidSelectors.merge(invalidBatch) { current, _ in current }
    start = end
}

let reports = invalidSelectors.keys.sorted().map { selector in
    InvalidSelectorReport(
        selector: selector,
        error: invalidSelectors[selector] ?? "Unknown error",
        occurrences: selectorOccurrences[selector] ?? []
    )
}

let outputData = try JSONEncoder().encode(reports)
if let outputPath = options.outputPath {
    let outputURL = URL(fileURLWithPath: outputPath)
    try FileManager.default.createDirectory(
        at: outputURL.deletingLastPathComponent(),
        withIntermediateDirectories: true
    )
    try outputData.write(to: outputURL)
}

if let text = String(data: outputData, encoding: .utf8) {
    print(text)
}
