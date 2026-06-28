(ns rpg.ingest.stat-blocks-test
  (:require [clojure.test :refer [deftest is testing]]
            [rpg.ingest.extract.pdf :as pdf]
            [rpg.ingest.block-merging :as bm]
            [rpg.ingest.stat-blocks.core :as stat-core]
            [rpg.ingest.stat-blocks.registry :as registry]
            [rpg.ingest.test-fixtures.layout :as layout])
  (:import [java.io File]))

(defn- momie-pdf-path []
  (File. "../../data/pdfs/COF2_10_Mondanites_Et_Momies_web_v1a.pdf"))

(defn- momie-pages []
  (let [pdf (.getAbsolutePath (momie-pdf-path))
        extracted (pdf/extract-document pdf)
        profile (registry/resolve-profile "cof2" (:pages extracted))
        {:keys [pages]} (bm/merge-fragmented-pages (:pages extracted) profile)]
    (:pages (stat-core/annotate-stat-blocks profile pages))))

(deftest resolve-profile-cof2-aliases
  (testing "COF2 aliases resolve to :cof2 profile"
    (is (= :cof2 (registry/resolve-profile "cof2" nil)))
    (is (= :cof2 (registry/resolve-profile "chroniques oubliees fantasy 2" nil)))))

(deftest cof2-matches-mondanites-document
  (testing "Momie PDF auto-detects as COF2"
    (when (.exists (momie-pdf-path))
      (let [pages (:pages (pdf/extract-document (.getAbsolutePath (momie-pdf-path))))]
        (is (stat-core/matches-document? :cof2 pages))))))

(deftest parse-mondanites-page-15-like-python
  (testing "Page 15 stat blocks align with Python extraction"
    (when (.exists (momie-pdf-path))
      (let [pages (momie-pages)
            spans (:spans (stat-core/annotate-stat-blocks :cof2 pages))
            page-15-spans (filter #(= 15 (:page-start %)) spans)
            parsed (map #(stat-core/parse-span :cof2 %) page-15-spans)
            by-name (into {} (map (juxt :name identity) parsed))
            azulria (get by-name "AZULRIA")
            taless (get by-name "TALESS RHANN")]
        (is (= 2 (count page-15-spans)))
        (is (= 4 (:nc azulria)))
        (is (= "PRÊTRESSE 7" (:subtitle azulria)))
        (is (= {:AGI 1 :CON 2 :FOR 1 :PER 0 :CHA 0 :INT 0 :VOL 3} (:attributes azulria)))
        (is (= "momie" (get-in taless [:rulebook-reference :profile-name])))
        (is (= 4 (count (:abilities taless))))
        (is (every? #(pos? (count (:text %))) (:abilities taless)))))))

(deftest false-heading-skips-stat-line
  (testing "COF2 profile treats NC line as false heading"
    (let [page (layout/make-page [(layout/make-block 1 0 "| NC 4 AZULRIA" 12)])
          block (first (:blocks page))]
      (is (stat-core/false-heading? :cof2 block (:blocks page) 0 page)))))
