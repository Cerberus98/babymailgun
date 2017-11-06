package main

import (
	"crypto/rand"
	"fmt"
	"github.com/cerberus98/babymailgun/internal"
	"github.com/spf13/viper"
	"log"
	"os"
	"os/signal"
	"sync"
	"syscall"
	"time"
)

type WorkerConfig struct {
	Host         string
	Port         string
	DatabaseName string
	WorkerSleep  int
}

// Create a UUID4. Source implementation here: https://groups.google.com/forum/#!msg/golang-nuts/d0nF_k4dSx4/rPGgfXv6QCoJ
func uuid() string {
	b := make([]byte, 16)
	rand.Read(b)
	b[6] = (b[6] & 0x0f) | 0x40
	b[8] = (b[8] & 0x3f) | 0x80
	return fmt.Sprintf("%x-%x-%x-%x-%x", b[0:4], b[4:6], b[6:8], b[8:10], b[10:])
}

func processingLoop(cfg *WorkerConfig, wg *sync.WaitGroup, quit chan bool) {
	// Fetch emails ready to be sent
	// Try to send them
	// Update the datastore
	// Go back to sleep
	log.Println("Starting processing loop...")
	workerId := uuid()
	defer wg.Done()
loop:
	for {
		mongoClient := babymailgun.MongoClient{Host: cfg.Host, Port: cfg.Port, DatabaseName: cfg.DatabaseName}
		select {
		case <-quit:
			break loop
		default:
			log.Println("Waking up and looking for emails to send")
		}
		email, err := mongoClient.FetchReadyEmail(workerId)
		if err == nil {
			log.Printf("Got email %s Worker ID: %s\n", email.ID, workerId)
			// Try to send the email

			// Update the email status

			// Release the email
			log.Printf("Releasing email %s\n", email.ID)
			if err := mongoClient.ReleaseEmail(email); err != nil {
				// TODO Couldn't release the email, what do we do?
				log.Println(err)
			}
		} else {
			log.Printf("Error while fetching emails: %s, %t\n", err, err)
		}

		log.Printf("Going back to sleep for %d seconds\n", cfg.WorkerSleep)
		time.Sleep(time.Duration(cfg.WorkerSleep) * time.Second)
	}
	log.Println("Finishing up...")
}

func loadConfig() *WorkerConfig {
	viper.BindEnv("DB_HOST")
	viper.BindEnv("DB_PORT")
	viper.BindEnv("DB_NAME")
	viper.SetDefault("WORKER_SLEEP", 2)
	viper.BindEnv("WORKER_SLEEP")

	if !viper.IsSet("DB_HOST") {
		log.Fatal("Can't find necessary environment variable DB_HOST")
	}
	if !viper.IsSet("DB_PORT") {
		log.Fatal("Can't find necessary environment variable DB_PORT")
	}
	if !viper.IsSet("DB_NAME") {
		log.Fatal("Can't find necessary environment variable DB_NAME")
	}

	return &WorkerConfig{
		Host:         viper.GetString("db_host"),
		Port:         viper.GetString("db_port"),
		DatabaseName: viper.GetString("db_name"),
		WorkerSleep:  viper.GetInt("worker_sleep"),
	}
}

func main() {
	log.Println("Running worker")
	workerConfig := loadConfig()
	sigs := make(chan os.Signal, 1)
	quit := make(chan bool, 1)
	signal.Notify(sigs, syscall.SIGINT, syscall.SIGTERM)

	var wg sync.WaitGroup
	for i := 0; i < 5; i++ {
		go processingLoop(workerConfig, &wg, quit)
		wg.Add(1)
	}
	select {
	case <-sigs:
		quit <- true
	}
	wg.Wait()
	log.Println("Done")
}