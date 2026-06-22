(ns rpg.ingest.extract-test
  (:require [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.test-fixtures.pdf :as sample-pdf])
  (:import [java.io File]))

(deftest extract-page-reads-line-blocks
  (testing "PDF sample merges consecutive lines with the same font style"
    (let [temp-file (doto (File/createTempFile "rpg-ingest-" ".pdf")
                      (.deleteOnExit))
          pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath temp-file))
          page (pdf/extract-page pdf-path 1)]
      (is (= 1 (:page-number page)))
      (is (pos? (:width page)))
      (is (pos? (:height page)))
      (is (= 1 (count (:blocks page))))
      (is (re-find #"Premiere" (:text (first (:blocks page)))))
      (is (re-find #"Deuxieme" (:text (first (:blocks page))))))))

(deftest extract-page-keeps-block-metadata
  (testing "Each block exposes pdfbox_raw metadata and bbox"
    (let [temp-file (doto (File/createTempFile "rpg-ingest-meta-" ".pdf")
                      (.deleteOnExit))
          pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath temp-file))
          first-block (-> pdf-path (pdf/extract-page 1) :blocks first)]
      (is (= "pdfbox_raw" (:source (:metadata first-block))))
      (is (= "font-run" (:extraction (:metadata first-block))))
      (is (contains? (:bbox first-block) :x0))
      (is (pos? (:max-font-size (:metadata first-block)))))))

(deftest extract-page-splits-two-column-line-by-horizontal-gap
  (testing "Large horizontal gaps split a Y band; same-font lines merge within a column"
        (let [momie-pdf (java.io.File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
      (when (.exists momie-pdf)
        (let [page (pdf/extract-page (.getAbsolutePath momie-pdf) 7)
              block-count (count (:blocks page))
              texts (set (map :text (:blocks page)))]
          (is (< block-count 30)
              "page 7 should merge same-font lines within each column")
          (is (> block-count 4)
              "columns should still be split")
          (is (some #(str/includes? % "Dans les vestiges") texts))
          (is (some #(str/includes? % "Depuis lors") texts))
          (is (not (some #(and (str/includes? % "Dans les vestiges")
                               (str/includes? % "Depuis lors"))
                        texts))
              "left and right columns should not share the same block"))))))
