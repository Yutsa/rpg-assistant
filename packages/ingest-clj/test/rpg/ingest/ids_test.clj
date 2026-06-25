(ns rpg.ingest.ids-test
  (:require [clojure.test :refer [deftest is testing]]
            [rpg.ingest.ids :as ids])
  (:import [java.io File]))

(deftest new-id-format
  (testing "Prefixed ids use 12 hex chars"
    (let [id (ids/new-id "run")]
      (is (re-matches #"run_[0-9a-f]{12}" id)))))

(deftest document-id-from-hash-format
  (is (= "doc_abcdef012345"
         (ids/document-id-from-hash
          "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"))))

(deftest page-and-block-id-formats
  (is (= "page_doc_abc_0007" (ids/page-id "doc_abc" 7)))
  (is (= "block_doc_abc_007_003" (ids/page-block-id "doc_abc" 7 3))))

(deftest hash-file-stable
  (testing "SHA-256 hex digest is stable for the same content"
    (let [temp (doto (File/createTempFile "rpg-hash-" ".txt")
                 (.deleteOnExit))]
      (spit temp "phase-0-clojure-storage")
      (is (= (ids/hash-file (.getAbsolutePath temp))
             (ids/hash-file (.getAbsolutePath temp)))))))

(deftest hash-file-known-value
  (testing "Known SHA-256 for a fixed payload"
    (let [temp (doto (File/createTempFile "rpg-hash-known-" ".txt")
                 (.deleteOnExit))]
      (spit temp "momie")
      (is (= "5ed128bc47eb907fdc4d6711ad7d48af2f6c81a942d883a2c222fce1a801f77e"
             (ids/hash-file (.getAbsolutePath temp)))))))
