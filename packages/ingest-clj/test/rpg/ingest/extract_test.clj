(ns rpg.ingest.extract-test
  (:require [clojure.test :refer [deftest is testing]]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.test-fixtures.pdf :as sample-pdf])
  (:import [java.io File]))

(deftest extract-layout-reads-text-blocks
  (testing "PDF sample produces pages and text blocks"
    (let [temp-file (doto (File/createTempFile "rpg-ingest-" ".pdf")
                      (.deleteOnExit))
          pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath temp-file))
          layout-document (pdf/extract-layout pdf-path)
          first-page (first (:pages layout-document))]
      (is (= pdf-path (:source-path layout-document)))
      (is (= 1 (count (:pages layout-document))))
      (is (pos? (count (:blocks first-page))))
      (is (re-find #"Premiere" (:text first-page))))))

(deftest extract-layout-keeps-block-metadata
  (testing "Each block exposes pdfbox metadata"
    (let [temp-file (doto (File/createTempFile "rpg-ingest-meta-" ".pdf")
                      (.deleteOnExit))
          pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath temp-file))
          first-block (-> pdf-path pdf/extract-layout :pages first :blocks first)]
      (is (= "pdfbox" (:source (:metadata first-block))))
      (is (contains? (:bbox first-block) :x0))
      (is (pos? (:line-count (:metadata first-block)))))))

(deftest extract-layout-splits-two-columns
  (testing "Double-column pages produce separate left/right blocks"
    (let [temp-file (doto (File/createTempFile "rpg-ingest-columns-" ".pdf")
                      (.deleteOnExit))
          pdf-path (sample-pdf/create-two-column-pdf (.getAbsolutePath temp-file))
          page (-> pdf-path pdf/extract-layout :pages first)
          blocks (:blocks page)
          page-width (:width page)
          midpoint (/ page-width 2.0)]
      (is (>= (count blocks) 4))
      (is (some #(and (< (:x0 (:bbox %)) midpoint)
                      (re-find #"gauche" (:text %)))
                blocks))
      (is (some #(and (> (:x0 (:bbox %)) midpoint)
                      (re-find #"droite" (:text %)))
                blocks))
      (is (not (some #(and (< (:x0 (:bbox %)) midpoint)
                            (> (:x1 (:bbox %)) midpoint))
                     blocks))))))
