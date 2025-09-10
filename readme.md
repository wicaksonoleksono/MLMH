sudo ln -s /etc/nginx/sites-available/mentalhealth.conf /etc/nginx/sites-enabled/

sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d mentalhealth.laptopmerahputih.id -d www.mentalhealth.laptopmerahputih.id
