(ns rpg.ingest.chunks-test
  (:require [clojure.test :refer [deftest is testing]]
            [rpg.ingest.chunks :as chunks]
            [rpg.ingest.sections :as sections]
            [rpg.ingest.test-fixtures.layout :as layout]))

(defn- block
  [page idx text font-size & opts]
  (apply layout/make-block page idx text :font-size font-size opts))

(defn- build-chunks-for-pages [pages]
  (let [result (sections/assign-sections pages {:campaign-id "camp_test"
                                                :document-id "doc_test"})
        built (chunks/build-chunks-1to1 pages {:campaign-id "camp_test"
                                               :document-id "doc_test"
                                               :block-assignments (:block-assignments result)})]
    {:sections (chunks/refine-section-page-ends (:sections result) built)
     :chunks built
     :result result}))

(deftest build-chunks-partitions-blocks-between-headings-on-same-page
  (let [{:keys [chunks]} (build-chunks-for-pages
                          [(layout/make-page [(block 5 0 "EN QUELQUES MOTS" 14 :bold true :y0 10)
                                              (block 5 1 "Résumé court." 11 :y0 40)
                                              (block 5 2 "FICHE TECHNIQUE" 14 :bold true :y0 70)
                                              (block 5 3 "Niveau 5" 11 :y0 100)
                                              (block 5 4 "LES GRANDES LIGNES" 13 :bold true :y0 130)
                                              (block 5 5 "Contenu principal." 11 :y0 160)])])]
    (is (= 3 (count chunks)))
    (let [signatures (map chunks/chunk-block-signature chunks)]
      (is (= 3 (count (set signatures)))))
    (is (= 0 (:duplicate-chunk-count (chunks/chunk-uniqueness-stats chunks))))
    (is (= "Résumé court." (:text (first chunks))))
    (is (= "Niveau 5" (:text (second chunks))))
    (is (= "Contenu principal." (:text (nth chunks 2))))))

(deftest build-chunks-covers-all-blocks-without-duplicates
  (let [pages [(layout/make-page [(block 1 0 "Chapter 1" 18 :bold true :y0 10)
                                  (block 1 1 "First paragraph." 11 :y0 40)
                                  (block 1 2 "Second paragraph." 11 :y0 70)])
               (layout/make-page [(block 2 0 "Chapter 2" 18 :bold true :y0 10)
                                  (block 2 1 "Third paragraph." 11 :y0 40)]
                                 :page-number 2)]
        {:keys [chunks result]} (build-chunks-for-pages pages)
        heading-positions (set (:heading-anchors result))
        referenced (set (mapcat #(mapcat :page-block-ids (:source-spans %)) chunks))
        expected (set (for [page pages
                            block (:blocks page)
                            :when (not (contains? heading-positions
                                                  [(:page-number page) (:block-index block)]))]
                        (format "block_doc_test_%03d_%03d"
                                (:page-number page)
                                (:block-index block))))]
    (is (= expected referenced))
    (is (= 0 (:duplicate-chunk-count (chunks/chunk-uniqueness-stats chunks))))))

(deftest refine-section-page-ends-tightens-from-chunks
  (let [sections [{:id "sec_a" :page-start 1 :page-end 5}
                  {:id "sec_b" :page-start 2 :page-end 10}]
        chunks [{:section-id "sec_a" :page-end 3}
                {:section-id "sec_b" :page-end 4}
                {:section-id "sec_b" :page-end 7}]]
    (let [refined (chunks/refine-section-page-ends sections chunks)]
      (is (= 3 (:page-end (first refined))))
      (is (= 7 (:page-end (second refined)))))))
