package main

import (
    "github.com/gorilla/mux"
    "net/http"
)

func handleUsers(w http.ResponseWriter, r *http.Request) {
    w.Write([]byte("users"))
}

func handleAuth(w http.ResponseWriter, r *http.Request) {
    w.Write([]byte("auth"))
}

func main() {
    r := mux.NewRouter()
    r.HandleFunc("/users", handleUsers)
    r.HandleFunc("/auth", handleAuth)
}