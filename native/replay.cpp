// Owned compact-array conformance backend. No third-party index code.
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <string>
#include <vector>
using I=__int128_t;
struct Piece { I lo,hi,a,b,q,low,high; };
static void require(bool v,const char* m){if(!v) throw std::runtime_error(m);}
static I add(I a,I b){I r;require(!__builtin_add_overflow(a,b,&r),"addition admission");return r;}
static I mul(I a,I b){I r;require(!__builtin_mul_overflow(a,b,&r),"multiplication admission");return r;}
static I integer(){
    std::string s;require(bool(std::cin>>s),"missing integer");
    bool neg=s[0]=='-';size_t k=neg?1:0;require(k<s.size()&&s.size()<40,"integer length");
    I v=0;for(;k<s.size();++k){require(s[k]>='0'&&s[k]<='9',"integer syntax");v=add(mul(v,10),s[k]-'0');}
    require(v<(I(1)<<120),"native integer admission");return neg?-v:v;
}
static int small(int limit){I v=integer();require(v>=0&&v<=limit,"count admission");return int(v);}
static std::int64_t key(){I v=integer();require(v>=std::numeric_limits<std::int64_t>::min()&&v<=std::numeric_limits<std::int64_t>::max(),"key admission");return std::int64_t(v);}
static I predict(const Piece&s,I x){
    I num=add(mul(s.a,x),s.b);I d=num/s.q;return num<0&&num%s.q?d-1:d;
}
static int search(const std::vector<std::int64_t>&v,std::int64_t x,int lo,int hi,std::uint64_t&probes){
    while(lo<=hi){int mid=lo+(hi-lo)/2;++probes;if(v[mid]==x)return mid;if(v[mid]<x)lo=mid+1;else hi=mid-1;}return -1;
}
int main(){try{
    int mode=small(2),n=small(100000),m=small(100000),p=small(100000);require(p>0,"empty pieces");
    std::vector<std::int64_t>s(n),t(m);for(auto&x:s)x=key();for(auto&x:t)x=key();
    require(std::is_sorted(s.begin(),s.end())&&std::adjacent_find(s.begin(),s.end())==s.end(),"source set");
    require(std::is_sorted(t.begin(),t.end())&&std::adjacent_find(t.begin(),t.end())==t.end(),"target set");
    std::vector<Piece>pieces;for(int j=0;j<p;++j){Piece z{integer(),integer(),integer(),integer(),integer(),integer(),integer()};
        require(z.lo<=z.hi&&z.q>0&&z.low<=z.high,"piece admission");
        if(j)require(z.lo==pieces.back().hi+1,"routing gap");pieces.push_back(z);}
    std::string trailing;require(!(std::cin>>trailing),"trailing input");
    for(auto x:s)require(x>=pieces.front().lo&&x<=pieces.back().hi,"source domain");
    for(auto x:t)require(x>=pieces.front().lo&&x<=pieces.back().hi,"target domain");
    std::vector<std::int64_t>deletes,inserts;
    std::set_difference(s.begin(),s.end(),t.begin(),t.end(),std::back_inserter(deletes));
    std::set_difference(t.begin(),t.end(),s.begin(),s.end(),std::back_inserter(inserts));
    auto active=s;std::uint64_t queries=0,probes=0,misses=0,fallbacks=0,failed=0,moves=0,checksum=0;
    int prefixes=0;std::cout<<"{\"prefixes\":[";
    auto visit=[&](){
        size_t j=0;std::uint64_t q0=queries,p0=probes,miss0=misses;
        for(size_t rank=0;rank<active.size();++rank){auto x=active[rank];if(mode)while(x>pieces[j].hi)++j;
            int lo=0,hi=int(active.size())-1;
            if(mode){I pred=predict(pieces[j],x);I l=std::max(I(0),add(pred,pieces[j].low)),h=std::min(I(hi),add(pred,pieces[j].high));
                lo=l>hi?hi+1:int(l);hi=h<0?-1:int(h);}
            int found=search(active,x,lo,hi,probes);++queries;
            if(found<0){++misses;if(mode==2){++fallbacks;found=search(active,x,0,int(active.size())-1,probes);}}
            failed+=found!=int(rank);checksum=checksum*UINT64_C(6364136223846793005)+std::uint64_t(x)+rank;
        }
        if(prefixes++)std::cout<<',';
        std::cout<<"["<<active.size()<<','<<queries-q0<<','<<probes-p0<<','<<misses-miss0<<"]";
    };
    visit();for(auto x:deletes){auto at=std::lower_bound(active.begin(),active.end(),x);require(at!=active.end()&&*at==x,"inactive delete");
        moves+=active.end()-at-1;active.erase(at);visit();}
    for(auto x:inserts){auto at=std::lower_bound(active.begin(),active.end(),x);require(at==active.end()||*at!=x,"active insert");
        moves+=active.end()-at;active.insert(at,x);visit();}
    require(active==t,"final state mismatch");
    std::cout<<"],\"queries\":"<<queries<<",\"probes\":"<<probes<<",\"window_misses\":"<<misses
             <<",\"fallbacks\":"<<fallbacks<<",\"failed\":"<<failed<<",\"moves\":"<<moves
             <<",\"edits\":"<<deletes.size()+inserts.size()<<",\"checksum\":"<<checksum<<"}\n";
    return failed?3:0;
}catch(const std::exception&e){std::cerr<<e.what()<<'\n';return 2;}}
