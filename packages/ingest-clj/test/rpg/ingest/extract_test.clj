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

(deftest extract-page-keeps-single-block-on-same-line-font-change
  (testing "Font changes within one line stay in the same block"
    (let [temp-file (doto (File/createTempFile "rpg-ingest-mixed-font-" ".pdf")
                      (.deleteOnExit))
          pdf-path (sample-pdf/create-mixed-font-line-pdf (.getAbsolutePath temp-file))
          page (pdf/extract-page pdf-path 1)
          first-block (first (:blocks page))]
      (is (= 1 (count (:blocks page))))
      (is (re-find #"Normal bold text" (:text first-block))))))

(deftest extract-page-keeps-block-metadata
  (testing "Each block exposes pdfbox_raw metadata and bbox"
    (let [temp-file (doto (File/createTempFile "rpg-ingest-meta-" ".pdf")
                      (.deleteOnExit))
          pdf-path (sample-pdf/create-sample-pdf (.getAbsolutePath temp-file))
          first-block (-> pdf-path (pdf/extract-page 1) :blocks first)]
      (is (= "pdfbox_raw" (:source (:metadata first-block))))
      (is (= "paragraph" (:extraction (:metadata first-block))))
      (is (contains? (:bbox first-block) :x0))
      (is (pos? (:max-font-size (:metadata first-block)))))))

(deftest extract-page-splits-two-column-line-by-horizontal-gap
  (testing "Columns split by horizontal gap; paragraphs split by vertical rhythm"
        (let [momie-pdf (java.io.File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
      (when (.exists momie-pdf)
        (let [page (pdf/extract-page (.getAbsolutePath momie-pdf) 7)
              block-count (count (:blocks page))
              texts (set (map :text (:blocks page)))]
          (is (< block-count 40)
              "page 7 should not merge the whole column into one block per side")
          (is (> block-count 7)
              "page 7 should split body text into multiple paragraphs")
          (is (some #(str/includes? % "Dans les vestiges") texts))
          (is (some #(str/includes? % "Depuis lors") texts))
          (is (not (some #(and (str/includes? % "Dans les vestiges")
                               (str/includes? % "Depuis lors"))
                        texts))
              "left and right columns should not share the same block"))))))

(deftest extract-page-filters-parasite-blocks
  (testing "Running header, page numbers and DRM watermark are removed"
    (let [momie-pdf (java.io.File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
      (when (.exists momie-pdf)
        (let [page (pdf/extract-page (.getAbsolutePath momie-pdf) 9)
              texts (set (map :text (:blocks page)))]
          (is (= 5 (count (:blocks page))))
          (is (not (some #(re-find #"(?i)PAGE\s+\d+" %) texts)))
          (is (not (some #(re-find #"(?i)@" %) texts)))
          (is (not (some #(str/includes? % "Mondanités et momie") texts)))
          (is (some #(str/includes? % "Le manoir Horsbi") texts)))))))

(deftest extract-page-momie-p17-no-running-header-merge
  (testing "Running header must not merge into body continuation on page 17"
    (let [momie-pdf (java.io.File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
      (when (.exists momie-pdf)
        (let [page (pdf/extract-page (.getAbsolutePath momie-pdf) 17)
              first-left (first (filter #(str/includes? (:text %) "casque")
                                        (:blocks page)))]
          (is (some? first-left)
              "body continuation from page 16 should be present")
          (is (not (str/includes? (:text first-left) "Mondanités et momie"))
              "running header must not be merged into the body block")
          (is (> (:y0 (:bbox first-left)) (* (:height page) 0.05))
              "body block y0 must not extend into the header margin"))))))

(deftest extract-page-merges-multi-line-chip-entries
  (testing "Layout bullet detection splits NPC entries; multi-line descriptions stay merged"
    (let [momie-pdf (java.io.File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
      (when (.exists momie-pdf)
        (let [page (pdf/extract-page (.getAbsolutePath momie-pdf) 8)
              blocks (:blocks page)
              texts (map :text blocks)
              kalian-block (some #(when (str/includes? (:text %) "Kalian") %) blocks)
              taless-block (some #(when (str/includes? (:text %) "Taless Rhann") %) blocks)
              elsirianne-block (some #(when (str/includes? (:text %) "Elsirianne Horsbi") %) blocks)]
          (is (some? kalian-block)
              "Kalian entry should be present")
          (is (:list-item-start (:metadata kalian-block))
              "Kalian first segment should expose list-item-start metadata")
          (is (and (str/includes? (:text kalian-block) "témoin capital")
                   (str/includes? (:text kalian-block) "de la soirée"))
              "Kalian description should be one block, not split across lines")
          (is (not (some #(and (str/includes? % "Kalian")
                               (str/includes? % "Hector Debranne"))
                        texts))
              "Kalian and Hector should not share the same block")
          (is (and (str/includes? (:text taless-block) "Roi‑Sorcier")
                   (str/includes? (:text taless-block) "momie"))
              "Taless Rhann multi-line chip should be one block")
          (is (and (str/includes? (:text elsirianne-block) "collectionneuse")
                   (str/includes? (:text elsirianne-block) "Roi‑Sorcier"))
              "Elsirianne multi-line chip should be one block"))))))

(deftest extract-page-list-bullets-no-chip-entry-false-positives
  (testing "Body prose with mid-sentence colon is not split by chip-entry regex"
    (let [momie-pdf (java.io.File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
      (when (.exists momie-pdf)
        (let [page (pdf/extract-page (.getAbsolutePath momie-pdf) 10)
              texts (map :text (:blocks page))
              tempete-title (some #(when (and (str/includes? % "TEMPÊTE DE SABLE")
                                              (not (str/includes? % "La momie a déclenché")))
                                    %) texts)
              tempete-body (some #(when (str/includes? % "La momie a déclenché") %) texts)]
          (is (some? tempete-title)
              "TEMPÊTE DE SABLE encadré title should be present")
          (is (some? tempete-body)
              "encadré body should be a separate block from the title")
          (is (not (some #(re-find #"^[\s:]" (str/trim %)) texts))
              "no block should start with a fragment cut at a mid-sentence colon"))))))

(deftest extract-page-merges-illustration-wrap-fragments-in-same-column
  (testing "Indented line continuations around an illustration stay in the left-column block"
    (let [momie-pdf (java.io.File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
      (when (.exists momie-pdf)
        (let [page (pdf/extract-page (.getAbsolutePath momie-pdf) 14)
              texts (map :text (:blocks page))
              left-intro (some #(when (str/includes? % "En pénétrant dans la maison") %) texts)
              right-continuation (some #(when (str/includes? % "émaner. Proférant") %) texts)]
          (is (some? left-intro)
              "left-column intro block should be present")
          (is (and (str/includes? left-intro "vous ressen")
                   (str/includes? left-intro "tez immédiatement une")
                   (str/includes? left-intro "aura de terreur en"))
              "hyphenation and illustration indent fragments merge in the left column")
          (is (some? right-continuation)
              "right-column continuation should be a separate block")
          (is (not (str/includes? right-continuation "En pénétrant dans la maison"))
              "right-column block must not span columns")
          (is (not (some #(and (str/includes? % "tez immédiatement une")
                               (str/includes? % "émaner. Proférant"))
                        texts))
              "orphan fragments should not remain as standalone blocks"))))))

(deftest extract-page-handles-drop-cap-paragraph
  (testing "Drop-cap letter joins the wrapped first line, then full-width lines follow"
    (let [temp-file (doto (File/createTempFile "rpg-ingest-drop-cap-" ".pdf")
                      (.deleteOnExit))
          pdf-path (sample-pdf/create-drop-cap-paragraph-pdf (.getAbsolutePath temp-file))
          page (pdf/extract-page pdf-path 1)
          intro-block (first (:blocks page))]
      (is (= 1 (count (:blocks page))))
      (is (re-find #"^Si beaucoup ont oublie" (:text intro-block)))
      (is (re-find #"Terres d'Osgild" (:text intro-block)))
      (is (not (re-find #"STerres" (:text intro-block)))))))

(deftest extract-page-momie-p5-intro-drop-cap
  (testing "Page 5 intro paragraph keeps drop-cap reading order"
    (let [momie-pdf (java.io.File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
      (when (.exists momie-pdf)
        (let [page (pdf/extract-page (.getAbsolutePath momie-pdf) 5)
              intro-block (some #(when (and (str/includes? % "Terres d")
                                            (str/includes? % "Osgild"))
                                   %)
                                (map :text (:blocks page)))]
          (is (some? intro-block)
              "intro paragraph with Terres d'Osgild should be present")
          (is (re-find #"^Si beaucoup ont oublié" intro-block)
              "drop cap S should prefix the wrapped first line")
          (is (not (re-find #"STerres" intro-block))
              "drop cap must not merge into the next full-width line"))))))
