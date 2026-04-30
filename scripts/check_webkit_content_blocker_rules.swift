#!/usr/bin/env swift

import Foundation
import WebKit

struct BlockRule: Decodable {
    let id: String
    let name: String
    let scope: String
    let matchKind: String
    let pattern: String
    let isEnabled: Bool
    let literalOperator: String?
}

struct MergedFilterFile: Decodable {
    let webBlockFilterVersion: String
    let blockRules: [BlockRule]

    enum CodingKeys: String, CodingKey {
        case webBlockFilterVersion = "web-block-filter-version"
        case blockRules = "block-rules"
    }
}

struct ProgramOptions {
    var inputPaths: [String] = []
    var outputPath: String?
    var batchSize = 512
    var regexes: [String] = []
    var includeNonRegexRules = false
}

struct ValidationCandidate {
    let source: String
    let id: String
    let name: String
    let scope: String
    let matchKind: String
    let pattern: String
    let urlFilter: String
}

struct ValidationFailure: Encodable {
    let source: String
    let id: String
    let name: String
    let scope: String
    let matchKind: String
    let pattern: String
    let urlFilter: String
    let error: String
}

struct SourceSummary: Encodable {
    let source: String
    let checked: Int
    let failed: Int
}

struct ValidationReport: Encodable {
    let checked: Int
    let failed: Int
    let batchSize: Int
    let summaries: [SourceSummary]
    let failures: [ValidationFailure]
}

func waitUntil(_ condition: @autoclosure () -> Bool) {
    while !condition() {
        RunLoop.current.run(mode: .default, before: Date(timeIntervalSinceNow: 0.01))
    }
}

func parseArgs() -> ProgramOptions {
    var options = ProgramOptions()
    let arguments = CommandLine.arguments
    var index = 1

    while index < arguments.count {
        let argument = arguments[index]
        switch argument {
        case "--input":
            index += 1
            options.inputPaths.append(arguments[index])
        case "--output":
            index += 1
            options.outputPath = arguments[index]
        case "--batch-size":
            index += 1
            options.batchSize = Int(arguments[index]) ?? options.batchSize
        case "--regex":
            index += 1
            options.regexes.append(arguments[index])
        case "--include-non-regex-rules":
            options.includeNonRegexRules = true
        default:
            fputs("unknown argument: \(argument)\n", stderr)
            exit(2)
        }
        index += 1
    }

    if options.batchSize <= 0 {
        fputs("--batch-size must be greater than zero\n", stderr)
        exit(2)
    }

    if options.inputPaths.isEmpty && options.regexes.isEmpty {
        fputs("provide at least one --input or --regex\n", stderr)
        exit(2)
    }

    return options
}

func escapedLiteralContainsRegex(_ text: String) -> String {
    NSRegularExpression.escapedPattern(for: text)
}

func escapedURLExactRegex(_ text: String) -> String {
    "^\(NSRegularExpression.escapedPattern(for: text))$"
}

func escapedFQDNExactRegex(_ text: String) -> String {
    let escaped = NSRegularExpression.escapedPattern(for: text)
    return "^[A-Za-z][A-Za-z0-9+.-]*://(?:[^/]+\\\\.)?\(escaped)(?::[0-9]+)?(?:[/?#]|$)"
}

func makeURLFilter(from rule: BlockRule) -> String? {
    switch (rule.scope, rule.matchKind, rule.literalOperator) {
    case ("url", "regex", _):
        return rule.pattern
    case ("url", "literal", "contains"):
        return escapedLiteralContainsRegex(rule.pattern)
    case ("url", "literal", "exact"):
        return escapedURLExactRegex(rule.pattern)
    case ("fqdn", "literal", "exact"):
        return escapedFQDNExactRegex(rule.pattern)
    default:
        return nil
    }
}

func makeSyntheticRegexCandidates(_ regexes: [String]) -> [ValidationCandidate] {
    regexes.enumerated().map { index, regex in
        ValidationCandidate(
            source: "synthetic",
            id: "synthetic-\(index + 1)",
            name: regex,
            scope: "url",
            matchKind: "regex",
            pattern: regex,
            urlFilter: regex
        )
    }
}

func loadCandidates(
    from inputPath: String,
    includeNonRegexRules: Bool
) throws -> [ValidationCandidate] {
    let inputURL = URL(fileURLWithPath: inputPath)
    let data = try Data(contentsOf: inputURL)
    let decoder = JSONDecoder()
    let merged = try decoder.decode(MergedFilterFile.self, from: data)

    return merged.blockRules.compactMap { rule in
        if !rule.isEnabled {
            return nil
        }
        if !includeNonRegexRules && rule.matchKind != "regex" {
            return nil
        }
        guard let urlFilter = makeURLFilter(from: rule) else {
            return nil
        }
        return ValidationCandidate(
            source: inputPath,
            id: rule.id,
            name: rule.name,
            scope: rule.scope,
            matchKind: rule.matchKind,
            pattern: rule.pattern,
            urlFilter: urlFilter
        )
    }
}

func encodedContentRuleList(for candidates: ArraySlice<ValidationCandidate>) throws -> String {
    let payload = candidates.map { candidate in
        [
            "trigger": [
                "url-filter": candidate.urlFilter,
            ],
            "action": [
                "type": "block",
            ],
        ]
    }
    let data = try JSONSerialization.data(withJSONObject: payload, options: [])
    guard let text = String(data: data, encoding: .utf8) else {
        throw NSError(
            domain: "ContentRuleCheck",
            code: 1,
            userInfo: [NSLocalizedDescriptionKey: "failed to encode content rule list"]
        )
    }
    return text
}

func compileCandidates(_ candidates: ArraySlice<ValidationCandidate>) throws {
    let storeDirectory = URL(fileURLWithPath: "/tmp/webkit-content-rule-list-store", isDirectory: true)
    try FileManager.default.createDirectory(
        at: storeDirectory,
        withIntermediateDirectories: true
    )
    guard let store = WKContentRuleListStore(url: storeDirectory) else {
        throw NSError(
            domain: "ContentRuleCheck",
            code: 2,
            userInfo: [NSLocalizedDescriptionKey: "failed to create WKContentRuleListStore"]
        )
    }
    let identifier = "content-rule-check-\(UUID().uuidString)"
    let encoded = try encodedContentRuleList(for: candidates)

    var compileError: Error?
    var didFinishCompile = false

    store.compileContentRuleList(
        forIdentifier: identifier,
        encodedContentRuleList: encoded
    ) { _, error in
        compileError = error
        didFinishCompile = true
    }
    waitUntil(didFinishCompile)

    var didFinishCleanup = false
    store.removeContentRuleList(forIdentifier: identifier) { _ in
        didFinishCleanup = true
    }
    waitUntil(didFinishCleanup)

    if let compileError {
        throw compileError
    }
}

func collectFailures(
    candidates: [ValidationCandidate],
    range: Range<Int>
) -> [ValidationFailure] {
    if range.isEmpty {
        return []
    }

    let slice = candidates[range]
    do {
        try compileCandidates(slice)
        return []
    } catch {
        if range.count == 1, let candidate = slice.first {
            return [
                ValidationFailure(
                    source: candidate.source,
                    id: candidate.id,
                    name: candidate.name,
                    scope: candidate.scope,
                    matchKind: candidate.matchKind,
                    pattern: candidate.pattern,
                    urlFilter: candidate.urlFilter,
                    error: String(describing: error)
                )
            ]
        }

        let midpoint = range.lowerBound + (range.count / 2)
        return collectFailures(candidates: candidates, range: range.lowerBound..<midpoint)
            + collectFailures(candidates: candidates, range: midpoint..<range.upperBound)
    }
}

func validateCandidates(
    _ candidates: [ValidationCandidate],
    batchSize: Int
) -> [ValidationFailure] {
    var failures: [ValidationFailure] = []
    var start = 0

    while start < candidates.count {
        let end = min(start + batchSize, candidates.count)
        let batchRange = start..<end
        let batchFailures = collectFailures(candidates: candidates, range: batchRange)
        failures.append(contentsOf: batchFailures)
        fputs(
            "checked \(end)/\(candidates.count), failures \(failures.count)\n",
            stderr
        )
        start = end
    }

    return failures
}

func makeSourceSummaries(
    candidates: [ValidationCandidate],
    failures: [ValidationFailure]
) -> [SourceSummary] {
    let groupedChecked = Dictionary(grouping: candidates, by: \.source)
    let groupedFailures = Dictionary(grouping: failures, by: \.source)
    let sources = Set(groupedChecked.keys).union(groupedFailures.keys).sorted()

    return sources.map { source in
        SourceSummary(
            source: source,
            checked: groupedChecked[source]?.count ?? 0,
            failed: groupedFailures[source]?.count ?? 0
        )
    }
}

let options = parseArgs()

var candidates: [ValidationCandidate] = []
for inputPath in options.inputPaths {
    candidates.append(
        contentsOf: try loadCandidates(
            from: inputPath,
            includeNonRegexRules: options.includeNonRegexRules
        )
    )
}
candidates.append(contentsOf: makeSyntheticRegexCandidates(options.regexes))

let failures = validateCandidates(candidates, batchSize: options.batchSize)
let report = ValidationReport(
    checked: candidates.count,
    failed: failures.count,
    batchSize: options.batchSize,
    summaries: makeSourceSummaries(candidates: candidates, failures: failures),
    failures: failures
)

let outputData = try JSONEncoder().encode(report)
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
