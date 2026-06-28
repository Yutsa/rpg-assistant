(ns rpg.ingest.block-merging-test
  (:require [clojure.test :refer [deftest is testing]]
            [rpg.ingest.block-merging :as merge]
            [rpg.ingest.chunks :as chunks]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.sections :as sections]
            [rpg.ingest.test-fixtures.layout :as layout]))

(defn- block [page idx text font-size & opts]
  (apply layout/make-block page idx text :font-size font-size opts))

(deftest merge-spread-title-pair-on-page-5
  (let [momie (java.io.File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [raw-page (pdf/extract-page (.getAbsolutePath momie) 5)
            merged (:pages (merge/merge-fragmented-pages [raw-page]))
            page (first merged)
            spread-blocks (filter #(re-find #"MONDANIT" (:text %)) (:blocks page))]
        (is (= 1 (count spread-blocks))
            "MONDANITÉS + ET MOMIE should become one block")
        (is (re-find #"MONDANITÉS" (:text (first spread-blocks))))
        (is (re-find #"ET MOMIE" (:text (first spread-blocks))))))))

(deftest merge-fiche-technique-body-on-page-5
  (let [momie (java.io.File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [raw-page (pdf/extract-page (.getAbsolutePath momie) 5)
            merged (:pages (merge/merge-fragmented-pages [raw-page]))
            page (first merged)
            fiche-heading (first (filter #(= "FICHE TECHNIQUE" (:text %)) (:blocks page)))
            fiche-body-blocks
            (filter #(and (not= (:text %) "FICHE TECHNIQUE")
                          (re-find #"Action/Enquête|Ambiance|Interaction|Investigation"
                                   (:text %)))
                    (:blocks page))]
        (is (some? fiche-heading)
            "FICHE TECHNIQUE heading stays separate")
        (is (= 1 (count fiche-body-blocks))
            "fiche body lines should merge into one block")
        (let [body-text (:text (first fiche-body-blocks))]
          (is (re-find #"Action/Enquête" body-text))
          (is (re-find #"Ambiance" body-text))
          (is (re-find #"Interaction" body-text))
          (is (re-find #"Investigation" body-text)))))))

(deftest page-5-chunks-have-single-spread-title-and-fiche-body
  (let [momie (java.io.File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [raw-page (pdf/extract-page (.getAbsolutePath momie) 5)
            {:keys [pages]} (merge/merge-fragmented-pages [raw-page])
            section-result (sections/assign-sections pages
                                                       {:campaign-id "momie"
                                                        :document-id "doc_test"})
            built-chunks (chunks/build-chunks-1to1 pages
                                                   {:campaign-id "momie"
                                                    :document-id "doc_test"
                                                    :block-assignments (:block-assignments section-result)})
            spread-chunks (filter #(and (re-find #"MONDANIT" (:text %))
                                        (re-find #"MOMIE" (:text %)))
                                  built-chunks)
            fiche-sec-id (:id (first (filter #(= "FICHE TECHNIQUE" (:title %))
                                             (:sections section-result))))
            fiche-chunks (filter #(= fiche-sec-id (:section-id %)) built-chunks)]
        (is (= 1 (count spread-chunks))
            "spread title should produce one chunk")
        (is (= 1 (count fiche-chunks))
            "FICHE TECHNIQUE section should have one body chunk")
        (is (re-find #"Action/Enquête" (:text (first fiche-chunks))))))))

(deftest wrap-around-merge-page-15-stat-block
  (let [blocks [(layout/make-block 15 0
                                  "PASSAGE DANS LA PIERRE :\nDeux fois par jour, la momie peut se déplacer dans toutes les"
                                  :font-size 10 :bold true :x0 51.0 :y0 512.0 :x1 213.8 :y1 559.8)
                (layout/make-block 15 1
                                  "directions. Elle peut emmener une personne avec elle grâce à ce pouvoir."
                                  :font-size 10 :x0 260.8 :y0 45.7 :x1 426.3 :y1 70.2)]
        page (layout/make-page blocks :width 500 :height 700)
        {:keys [pages merged-block-count]} (merge/merge-fragmented-pages [page] :cof2)
        merged (:blocks (first pages))]
    (is (pos? merged-block-count))
    (is (= 1 (count merged)))
    (is (re-find #"dans toutes les directions" (:text (first merged))))))

(deftest synthetic-page-5-block-assignments-still-valid
  (let [page (layout/make-page [(block 5 0 "MONDANITÉS" 42 :bold true :x0 104 :y0 36 :x1 384 :y1 88)
                                (block 5 1 "ET MOMIE" 42 :bold true :x0 139 :y0 82 :x1 333 :y1 134)
                                (block 5 2 "EN QUELQUES MOTS" 11 :bold true :x0 78 :y0 219 :x1 190 :y1 232)
                                (block 5 3 "Résumé." 9 :x0 48 :y0 237 :x1 222 :y1 300)
                                (block 5 4 "FICHE TECHNIQUE" 11 :bold true :x0 290 :y0 223 :x1 388 :y1 238)
                                (block 5 5 "Type • Action/Enquête\nPJ • Niveau 5/6" 9 :x0 262 :y0 243 :x1 360 :y1 270)
                                (block 5 6 "Ambiance" 9 :bold true :x0 262 :y0 297 :x1 310 :y1 308)
                                (block 5 7 "Interaction" 9 :bold true :x0 262 :y0 308 :x1 320 :y1 319)
                                (block 5 8 "Investigation" 9 :bold true :x0 262 :y0 319 :x1 330 :y1 330)
                                (block 5 9 "LES GRANDES LIGNES" 13 :bold true :x0 248 :y0 389 :x1 368 :y1 404)
                                (block 5 10 "Contenu principal." 9 :x0 248 :y0 406 :x1 433 :y1 567)]
                               :width 510 :height 650)
        {:keys [pages]} (merge/merge-fragmented-pages [page])
        merged-page (first pages)
        fiche-body (filter #(re-find #"Action/Enquête|Ambiance" (:text %)) (:blocks merged-page))]
    (is (= 1 (count (filter #(re-find #"MONDANIT" (:text %)) (:blocks merged-page)))))
    (is (= 1 (count fiche-body)))))
