(ns rpg.ingest.sections-test
  (:require [clojure.string :as str]
            [clojure.test :refer [deftest is testing]]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.sections :as sections]
            [rpg.ingest.test-fixtures.layout :as layout])
  (:import [java.io File]))

(defn- block
  [page idx text font-size & opts]
  (apply layout/make-block page idx text :font-size font-size opts))

(defn- assign [pages]
  (sections/assign-sections pages {:campaign-id "camp_test" :document-id "doc_test"}))

(deftest detect-sections-finds-chapter-headings
  (let [pages [(layout/make-page [(block 1 0 "Chapter 1" 18 :bold true)
                                  (block 1 1 "Intro body text here." 11)])
               (layout/make-page [(block 2 0 "Chapter 2" 18 :bold true)
                                  (block 2 1 "More content." 11)]
                                 :page-number 2)]
        result (assign pages)]
    (is (= 2 (count (:sections result))))
    (is (= "Chapter 1" (:title (first (:sections result)))))
    (is (= 1 (:level (first (:sections result)))))
    (is (= "Chapter 2" (:title (second (:sections result)))))
    (is (= [[1 0] [2 0]] (:heading-anchors result)))))

(deftest detect-sections-fallback-when-no-headings
  (let [result (assign [(layout/make-page [(block 1 0 "Plain paragraph without headings." 11)])])]
    (is (= 1 (count (:sections result))))
    (is (= "Document" (:title (first (:sections result)))))
    (is (= [] (:heading-anchors result)))))

(deftest detect-sections-rejects-single-character-drop-cap-heading
  (let [result (assign [(layout/make-page [(block 5 0 "S" 24 :bold true)
                                         (block 5 1 "i beaucoup ont oublié." 11)])])
        titles (map :title (:sections result))]
    (is (not (some #(= "S" %) titles)))))

(deftest detect-sections-keeps-three-character-bold-headings
  (let [result (assign [(layout/make-page [(block 1 0 "Fin" 16 :bold true)
                                         (block 1 1 "Notes here." 11)])])]
    (is (= ["Fin"] (map :title (:sections result))))))

(deftest detect-sections-rejects-decorative-spread-title
  (let [result (assign [(layout/make-page [(block 5 0 "MONDANITÉS" 42 :bold true :x0 104 :y0 36 :x1 384 :y1 88)
                                         (block 5 1 "ET MOMIE" 42 :bold true :x0 139 :y0 82 :x1 333 :y1 134)
                                         (block 5 2 "EN QUELQUES MOTS" 11 :bold true :x0 78 :y0 219 :x1 190 :y1 232)
                                         (block 5 3 "Résumé." 9 :x0 48 :y0 237 :x1 222 :y1 300)]
                                 :width 510 :height 650)])
        titles (map :title (:sections result))]
    (is (not (some #(= "MONDANITÉS" %) titles)))
    (is (not (some #(= "ET MOMIE" %) titles)))
    (is (some #(= "EN QUELQUES MOTS" %) titles))))

(deftest detect-sections-nests-subordinates-under-chapter
  (let [result (assign [(layout/make-page [(block 5 0 "Les grandes lignes" 13 :bold true :x0 248 :y0 389 :x1 368 :y1 404)
                                         (block 5 1 "PARTIE I :\nL'HISTOIRE EN UN COUP D'ŒIL" 14 :bold true :x0 43 :y0 459 :x1 225 :y1 489)
                                         (block 5 2 "Corps de la partie." 9 :x0 43 :y0 493 :x1 227 :y1 551)
                                         (block 5 3 "Les PJ sont invités." 9 :x0 248 :y0 406 :x1 433 :y1 567)]
                                 :width 510 :height 650)
                        (layout/make-page [(block 7 0 "L'histoire pour le MJ" 13 :bold true :x0 43 :y0 123 :x1 177 :y1 138)
                                         (block 7 1 "Secrets pour le MJ." 9 :x0 43 :y0 140 :x1 227 :y1 357)]
                                 :page-number 7 :width 510 :height 650)])
        partie (first (filter #(str/starts-with? (:title %) "PARTIE I") (:sections result)))
        grandes-lignes (first (filter #(= "Les grandes lignes" (:title %)) (:sections result)))
        histoire-mj (first (filter #(= "L'histoire pour le MJ" (:title %)) (:sections result)))]
    (is (nil? (:parent-section-id partie)))
    (is (= (:id partie) (:parent-section-id grandes-lignes)))
    (is (= (:id partie) (:parent-section-id histoire-mj)))))

(deftest detect-sections-finds-title-case-heading
  (let [result (assign [(layout/make-page [(block 5 0 "Les grandes lignes" 13 :bold true)
                                         (block 5 1 "Les PJ sont invités." 9)]
                                 :width 510 :height 650)])]
    (is (= ["Les grandes lignes"] (map :title (:sections result))))))

(deftest detect-sections-no-false-preamble-when-chapter-in-parallel-column
  (let [result (assign [(layout/make-page [(block 8 0 "Il est temps pour les PJ de découvrir la vérité." 9.5 :x0 43 :y0 46 :x1 227 :y1 90)
                                         (block 8 1 "Les différents acteurs" 13 :bold true :x0 43 :y0 250 :x1 200 :y1 265)
                                         (block 8 2 "• Kalian : marchand ambitieux." 9.5 :x0 43 :y0 270 :x1 227 :y1 300)
                                         (block 8 3 "• Hector : garde du corps." 9.5 :x0 248 :y0 46 :x1 433 :y1 76)
                                         (block 8 4 "• Elsirianne : érudite de Piémont." 9.5 :x0 248 :y0 80 :x1 433 :y1 110)
                                         (block 8 5 "PARTIE II :\nL'ENQUÊTE" 14 :bold true :x0 248 :y0 459 :x1 400 :y1 489)
                                         (block 8 6 "Corps de la partie II." 9.5 :x0 248 :y0 493 :x1 433 :y1 551)]
                                 :width 510 :height 650)])
        titles (map :title (:sections result))]
    (is (not (some #(= "Introduction" %) titles)))
    (is (some #(= "Les différents acteurs" %) titles))
    (is (some #(str/starts-with? % "PARTIE II") titles))))

(deftest detect-sections-keeps-same-page-subordinates-under-first-chapter
  (let [result (assign [(layout/make-page [(block 5 0 "PARTIE I :\nL'HISTOIRE" 14 :bold true :x0 43 :y0 100 :x1 225 :y1 130)
                                         (block 5 1 "Les grandes lignes" 15 :bold true :x0 248 :y0 150 :x1 368 :y1 165)
                                         (block 5 2 "Corps partie I." 9 :x0 43 :y0 170 :x1 227 :y1 220)
                                         (block 5 3 "PARTIE II :\nL'ENQUÊTE" 14 :bold true :x0 248 :y0 400 :x1 400 :y1 430)
                                         (block 5 4 "Corps partie II." 9 :x0 248 :y0 440 :x1 433 :y1 500)]
                                 :width 510 :height 650)])
        partie-i (first (filter #(str/starts-with? (:title %) "PARTIE I") (:sections result)))
        partie-ii (first (filter #(str/starts-with? (:title %) "PARTIE II") (:sections result)))
        grandes-lignes (first (filter #(= "Les grandes lignes" (:title %)) (:sections result)))]
    (is (= (:id partie-i) (:parent-section-id grandes-lignes)))
    (is (not= (:id partie-ii) (:parent-section-id grandes-lignes)))))

(deftest detect-sections-nests-numbered-heading-under-pre-chapter-title-case
  (let [result (assign [(layout/make-page [(block 16 0 "Les abattoirs" 15 :bold true :x0 43 :y0 200 :x1 150 :y1 215)
                                          (block 16 1 "1 - Cave de l'abattoir" 13 :bold true :x0 43 :y0 230 :x1 200 :y1 245)
                                          (block 16 2 "Description de la cave." 9 :x0 43 :y0 250 :x1 227 :y1 300)]
                                  :width 510 :height 650)])
        abattoirs (first (filter #(= "Les abattoirs" (:title %)) (:sections result)))
        cave (first (filter #(str/starts-with? (:title %) "1") (:sections result)))]
    (is (nil? (:parent-section-id abattoirs)))
    (is (= (:id abattoirs) (:parent-section-id cave)))))

(deftest detect-sections-rejects-two-character-bold-headings
  (let [result (assign [(layout/make-page [(block 1 0 "GM" 16 :bold true)
                                         (block 1 1 "Notes here." 11)])])]
    (is (= "Document" (:title (first (:sections result)))))))

(deftest block-assignments-page-5-synthetic
  (let [result (assign [(layout/make-page [(block 5 0 "MONDANITÉS" 42 :bold true :x0 104 :y0 36 :x1 384 :y1 88)
                                         (block 5 1 "ET MOMIE" 42 :bold true :x0 139 :y0 82 :x1 333 :y1 134)
                                         (block 5 2 "EN QUELQUES MOTS" 11 :bold true :x0 78 :y0 219 :x1 190 :y1 232)
                                         (block 5 3 "Résumé." 9 :x0 48 :y0 237 :x1 222 :y1 300)
                                         (block 5 4 "FICHE TECHNIQUE" 11 :bold true :x0 290 :y0 223 :x1 388 :y1 238)
                                         (block 5 5 "Niveau 5" 9 :x0 262 :y0 243 :x1 360 :y1 297)
                                         (block 5 6 "LES GRANDES LIGNES" 13 :bold true :x0 248 :y0 389 :x1 368 :y1 404)
                                         (block 5 7 "Contenu principal." 9 :x0 248 :y0 406 :x1 433 :y1 567)]
                                 :width 510 :height 650)])
        sections (:sections result)
        assignments (:block-assignments result)]
    (is (= 3 (count sections)))
    (is (= (:id (first (filter #(= "EN QUELQUES MOTS" (:title %)) sections)))
           (get assignments "block_doc_test_005_004")))
    (is (= (:id (first (filter #(= "FICHE TECHNIQUE" (:title %)) sections)))
           (get assignments "block_doc_test_005_005")))
    (is (= (:id (first (filter #(= "LES GRANDES LIGNES" (:title %)) sections)))
           (get assignments "block_doc_test_005_007")))))

(deftest momie-page-5-real-pdf-sections-and-assignments
  (let [momie (File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf")]
    (when (.exists momie)
      (let [page (pdf/extract-page (.getAbsolutePath momie) 5)
            result (assign [page])
            titles (set (map :title (:sections result)))
            body-assignments (count (:block-assignments result))]
        (is (contains? titles "EN QUELQUES MOTS"))
        (is (contains? titles "FICHE TECHNIQUE"))
        (is (not (contains? titles "MONDANITÉS")))
        (is (not (contains? titles "ET MOMIE")))
        (is (pos? body-assignments))))))
