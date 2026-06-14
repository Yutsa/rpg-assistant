(ns rpg-assistant-web.navigation-test
  (:require
   [cljs.test :refer-macros [deftest is testing are]]
   [rpg-assistant-web.router :as router]
   [rpg-assistant-web.test-helpers :as h]
   [rpg-assistant-web.views :as views]))

(def sample-campaigns
  [{:id "momie" :title "Mondanités et Momie" :document_count 1 :game_system "cof2"}])

(defn- sample-state
  [location & {:keys [campaigns campaigns-loading? campaigns-error]
                 :or {campaigns sample-campaigns
                      campaigns-loading? false
                      campaigns-error nil}}]
  {:location location
   :campaigns campaigns
   :campaigns-loading? campaigns-loading?
   :campaigns-error campaigns-error})

(defn- render-at-path
  [path & {:keys [campaigns campaigns-loading? campaigns-error]}]
  (let [location (router/current-location-for-path path)]
    (views/render
     (cond-> (sample-state location)
       campaigns (assoc :campaigns campaigns)
       campaigns-loading? (assoc :campaigns-loading? campaigns-loading?)
       campaigns-error (assoc :campaigns-error campaigns-error)))))

(defn- simulate-link-navigation
  "Simule un clic intercepté sur un lien interne (route-click sans DOM)."
  [state href]
  (if-let [location (router/url->location router/routes href)]
    (assoc state :location location)
    state))

(deftest deep-link-does-not-show-campaign-list-test
  (testing "les URLs profondes n'affichent pas la liste des campagnes"
    (doseq [[path expected-title]
            [["/campaigns/momie" "Documents — momie"]
             ["/documents/doc_010672301b36" "Exploration — doc_010672301b36"]
             ["/documents/doc_010672301b36/chunks/chunk_1" "Exploration — doc_010672301b36"]
             ["/documents/doc_010672301b36/stat-blocks" "Fiches stats — doc_010672301b36"]
             [(router/location->url
               router/routes
               {:location/page-id :pages/stat-block-detail
                :location/params {:document-id "doc_1"
                                  :stat-block-name "Momie ancienne"}})
              "Momie ancienne"]]]
      (let [tree (render-at-path path)]
        (is (= expected-title (h/main-h2-text tree)) (str "titre pour " path))
        (is (not (h/shows-campaign-list? tree)) (str "pas de grille campagnes pour " path)))))

  (testing "seule la racine affiche la liste des campagnes"
    (doseq [path ["/" "/index.html"]]
      (let [tree (render-at-path path)]
        (is (h/shows-campaign-list? tree) (str "grille campagnes attendue pour " path))
        (is (= "Campagnes" (h/main-h2-text tree))))))

  (testing "chemin inconnu affiche la page introuvable, pas la liste"
    (let [tree (render-at-path "/inconnu")]
      (is (= "Page introuvable" (h/main-h2-text tree)))
      (is (not (h/shows-campaign-list? tree))))))

(deftest link-navigation-acceptance-test
  (testing "clic carte campagne → vue documents"
    (let [initial (sample-state {:location/page-id :pages/campaigns})
          tree (-> initial
                   (simulate-link-navigation "/campaigns/momie")
                   views/render)]
      (is (= "Documents — momie" (h/main-h2-text tree)))
      (is (not (h/shows-campaign-list? tree)))))

  (testing "clic fil d'Ariane document → vue exploration"
    (let [initial (sample-state (router/current-location-for-path "/documents/doc_1/stat-blocks"))
          tree (-> initial
                   (simulate-link-navigation "/documents/doc_1")
                   views/render)]
      (is (= "Exploration — doc_1" (h/main-h2-text tree)))
      (is (not (h/shows-campaign-list? tree)))))

  (testing "clic fil d'Ariane Campagnes → liste"
    (let [initial (sample-state (router/current-location-for-path "/campaigns/momie"))
          tree (-> initial
                   (simulate-link-navigation "/")
                   views/render)]
      (is (h/shows-campaign-list? tree))
      (is (= "Campagnes" (h/main-h2-text tree))))))

(deftest breadcrumb-hrefs-acceptance-test
  (testing "chaque entrée cliquable du fil d'Ariane a un href valide"
    (doseq [path ["/campaigns/momie"
                  "/documents/doc_1"
                  "/documents/doc_1/stat-blocks"
                  "/documents/doc_1/stat-blocks/Momie"]]
      (let [location (router/current-location-for-path path)
            crumbs (router/breadcrumbs location)]
        (doseq [{:keys [label location]} crumbs
                :when location]
          (let [href (router/location->url router/routes location)
                resolved (router/url->location router/routes href)]
            (is (seq href) (str "href manquant pour « " label " » depuis " path))
            (is (= (:location/page-id location) (:location/page-id resolved))
                (str "round-trip page-id pour « " label " »")))))))

  (testing "le lien Campagnes pointe vers /"
    (is (= "/"
           (router/location->url router/routes {:location/page-id :pages/campaigns})))))

(deftest url-resync-acceptance-test
  (testing "le rendu suit current-location-for-path (comme après popstate)"
    (doseq [[path expected-title shows-campaigns?]
            [["/campaigns/momie" "Documents — momie" false]
             ["/" "Campagnes" true]
             ["/index.html" "Campagnes" true]]]
      (let [location (router/current-location-for-path path)
            tree (views/render (sample-state location))]
        (is (= expected-title (h/main-h2-text tree)) path)
        (is (= shows-campaigns? (h/shows-campaign-list? tree)) path)))))
