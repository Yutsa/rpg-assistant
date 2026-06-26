(ns rpg.ingest.coverage-test
  (:require [clojure.test :refer [deftest is testing]]
            [rpg.ingest.coverage :as coverage]))

(deftest page-text-coverage-ratio-heuristic
  (testing "matches Python heuristic: char_count * 50 / page_area"
    (let [ratio (coverage/page-text-coverage-ratio "hello" 100.0 100.0)]
      (is (= 0.025 ratio)))
    (is (= 0.0 (coverage/page-text-coverage-ratio "" 100.0 100.0)))
    (is (= 0.0 (coverage/page-text-coverage-ratio "text" 0.0 100.0)))))

(deftest document-coverage-ratio-averages-pages
  (is (= 0.5 (coverage/document-coverage-ratio [0.2 0.8])))
  (is (= 0.0 (coverage/document-coverage-ratio []))))

(deftest scanned-or-unusable-uses-threshold
  (is (coverage/scanned-or-unusable? [0.1 0.15] 0.3))
  (is (not (coverage/scanned-or-unusable? [0.4 0.5] 0.3))))
